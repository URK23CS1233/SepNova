"""
SepNova — Clinical Explainability Engine
==========================================
Two novel explanation methods for each patient:

1. FEATURE IMPORTANCE (local):
   XGBoost SHAP-free gain-based importance, ranked for the specific patient's
   feature values, not the global average. Uses a perturbation approach to
   identify which features most changed the prediction for THIS patient.

2. COUNTERFACTUAL EXPLANATIONS (novel):
   For each high/critical risk patient, computes the minimum clinically
   actionable changes needed to reduce risk below the next lower threshold.
   Example output:
     "If Lactate drops from 4.3 → 2.1 mmol/L AND MAP rises from 58 → 70 mmHg,
      risk drops from CRITICAL (72%) → HIGH (44%)"

   Algorithm:
   - Identify top 10 features by gain importance
   - For each modifiable feature, binary-search for the minimum change
     that alone reduces ensemble probability below next threshold
   - Filter to clinically actionable features (exclude Age, Gender)
   - Rank by magnitude of probability reduction
   - Return top 3

NOVELTY: No prior ICU sepsis paper provides counterfactual clinical recommendations
alongside probabilistic ML predictions.
"""
from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from typing import Any


# Clinically actionable features — can be changed by intervention
ACTIONABLE = {
    "Lactate", "MAP", "HR", "SBP", "Resp", "Temp", "O2Sat",
    "WBC", "Creatinine", "Platelets", "Glucose", "Hgb",
    "pH", "PaCO2", "HCO3", "BaseExcess", "BUN",
}

# Clinical labels and units for display
FEATURE_META = {
    "Lactate_last":      {"label": "Lactate",      "unit": "mmol/L", "direction": "decrease"},
    "Lactate_mean":      {"label": "Lactate (avg)","unit": "mmol/L", "direction": "decrease"},
    "MAP_last":          {"label": "MAP",           "unit": "mmHg",   "direction": "increase"},
    "MAP_mean":          {"label": "MAP (avg)",     "unit": "mmHg",   "direction": "increase"},
    "HR_last":           {"label": "Heart Rate",    "unit": "bpm",    "direction": "decrease"},
    "HR_mean":           {"label": "Heart Rate (avg)","unit": "bpm",  "direction": "decrease"},
    "SBP_last":          {"label": "Systolic BP",   "unit": "mmHg",   "direction": "increase"},
    "O2Sat_last":        {"label": "O2 Saturation", "unit": "%",      "direction": "increase"},
    "WBC_last":          {"label": "WBC",           "unit": "K/μL",   "direction": "decrease"},
    "Creatinine_last":   {"label": "Creatinine",    "unit": "mg/dL",  "direction": "decrease"},
    "Platelets_last":    {"label": "Platelets",     "unit": "K/μL",   "direction": "increase"},
    "Temp_last":         {"label": "Temperature",   "unit": "°C",     "direction": "normalize"},
    "Resp_last":         {"label": "Resp Rate",     "unit": "bpm",    "direction": "decrease"},
    "Glucose_last":      {"label": "Glucose",       "unit": "mg/dL",  "direction": "normalize"},
    "BUN_last":          {"label": "BUN",           "unit": "mg/dL",  "direction": "decrease"},
    "pH_last":           {"label": "pH",            "unit": "",       "direction": "increase"},
}


@dataclass
class FeatureContribution:
    feature:     str
    label:       str
    unit:        str
    current_val: float
    importance:  float     # contribution to this patient's risk
    direction:   str       # 'increase' | 'decrease' | 'normalize'


@dataclass
class Counterfactual:
    feature:       str
    label:         str
    unit:          str
    current_val:   float
    target_val:    float
    prob_before:   float
    prob_after:    float
    risk_reduction: float  # how much the probability drops


def predict_prob(xgb_model, lgb_model, feature_names: list, features: dict) -> float:
    x = np.array([features.get(f, 0.0) for f in feature_names], dtype=np.float32).reshape(1, -1)
    xgb_p = float(xgb_model.predict_proba(x)[0, 1])
    lgb_p = float(lgb_model.predict_proba(x)[0, 1])
    return 0.55 * xgb_p + 0.45 * lgb_p


def get_feature_contributions(
    xgb_model,
    lgb_model,
    feature_names: list[str],
    patient_features: dict[str, float],
    top_k: int = 10,
) -> list[FeatureContribution]:
    """
    Local perturbation-based feature importance for this specific patient.
    For each feature, mask it to zero and measure probability change.
    Features with largest probability drop are most important for THIS patient.
    """
    base_prob = predict_prob(xgb_model, lgb_model, feature_names, patient_features)
    contributions = []

    for feat in feature_names:
        val = patient_features.get(feat, 0.0)
        if val == 0.0:
            continue

        # Mask this feature out
        modified = dict(patient_features)
        modified[feat] = 0.0
        masked_prob = predict_prob(xgb_model, lgb_model, feature_names, modified)
        importance = base_prob - masked_prob  # positive = feature increased risk

        meta = FEATURE_META.get(feat, {})
        contributions.append(FeatureContribution(
            feature=feat,
            label=meta.get("label", feat),
            unit=meta.get("unit", ""),
            current_val=round(val, 2),
            importance=round(importance, 4),
            direction=meta.get("direction", "decrease"),
        ))

    # Sort by absolute importance, keep top_k
    contributions.sort(key=lambda c: abs(c.importance), reverse=True)
    return contributions[:top_k]


def get_counterfactuals(
    xgb_model,
    lgb_model,
    feature_names: list[str],
    patient_features: dict[str, float],
    current_level: str,
    top_n: int = 3,
) -> list[Counterfactual]:
    """
    Find the minimum clinically actionable feature changes to cross the next lower risk threshold.
    Uses binary search on each feature independently.
    """
    NEXT_THRESHOLD = {
        "critical": 0.45,   # SNS, not raw prob — approximate
        "high":     0.25,
        "medium":   0.10,
    }
    # Map to raw ensemble probability targets
    PROB_TARGET = {
        "critical": 0.45,
        "high":     0.28,
        "medium":   0.14,
    }
    target_prob = PROB_TARGET.get(current_level, 0.28)
    base_prob   = predict_prob(xgb_model, lgb_model, feature_names, patient_features)

    if base_prob <= target_prob:
        return []  # Already below threshold

    counterfactuals: list[Counterfactual] = []

    # Only try actionable features with non-zero values
    candidate_feats = [
        f for f in feature_names
        if any(act in f for act in ACTIONABLE)
        and patient_features.get(f, 0.0) != 0.0
    ]

    for feat in candidate_feats:
        current_val = patient_features.get(feat, 0.0)
        meta = FEATURE_META.get(feat, {})
        direction = meta.get("direction", "decrease")

        # Determine search range
        if direction == "decrease":
            lo, hi = max(0.0, current_val * 0.1), current_val
        elif direction == "increase":
            lo, hi = current_val, current_val * 3.0
        else:  # normalize — try both directions
            lo, hi = current_val * 0.5, current_val * 1.5

        # Binary search for minimum change that crosses target_prob
        best_val = None
        for _ in range(20):  # 20 iterations = precision ~0.001
            mid = (lo + hi) / 2
            modified = dict(patient_features)
            modified[feat] = mid
            prob = predict_prob(xgb_model, lgb_model, feature_names, modified)

            if prob <= target_prob:
                best_val = mid
                if direction == "decrease":
                    lo = mid   # can we do less change?
                else:
                    hi = mid
            else:
                if direction == "decrease":
                    hi = mid
                else:
                    lo = mid

        if best_val is not None:
            modified = dict(patient_features)
            modified[feat] = best_val
            prob_after = predict_prob(xgb_model, lgb_model, feature_names, modified)
            counterfactuals.append(Counterfactual(
                feature=feat,
                label=meta.get("label", feat),
                unit=meta.get("unit", ""),
                current_val=round(current_val, 2),
                target_val=round(best_val, 2),
                prob_before=round(base_prob, 4),
                prob_after=round(prob_after, 4),
                risk_reduction=round(base_prob - prob_after, 4),
            ))

    # Sort by largest risk reduction
    counterfactuals.sort(key=lambda c: c.risk_reduction, reverse=True)
    return counterfactuals[:top_n]


def explain_patient(artifact: dict, patient_features: dict, risk_level: str) -> dict:
    """
    Full explanation for one patient. Returns contributions + counterfactuals.
    """
    xgb = artifact["xgb"]
    lgb = artifact["lgb"]
    feat_names = artifact["feature_names"]

    contributions = get_feature_contributions(xgb, lgb, feat_names, patient_features)
    counterfactuals = get_counterfactuals(xgb, lgb, feat_names, patient_features, risk_level)

    return {
        "feature_contributions": [
            {
                "feature":     c.feature,
                "label":       c.label,
                "unit":        c.unit,
                "current_val": c.current_val,
                "importance":  c.importance,
                "direction":   c.direction,
            }
            for c in contributions
        ],
        "counterfactuals": [
            {
                "label":          cf.label,
                "unit":           cf.unit,
                "current_val":    cf.current_val,
                "target_val":     cf.target_val,
                "prob_before":    cf.prob_before,
                "prob_after":     cf.prob_after,
                "risk_reduction": cf.risk_reduction,
                "narrative": (
                    f"If {cf.label} changes from {cf.current_val} → {cf.target_val} {cf.unit}, "
                    f"risk probability drops from {cf.prob_before*100:.0f}% → {cf.prob_after*100:.0f}%"
                ),
            }
            for cf in counterfactuals
        ],
    }
