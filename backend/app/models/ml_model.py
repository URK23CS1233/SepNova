"""
SepNova Model Loader
=====================
Unified interface over three artifact generations:
  • v1  — XGB + LGB weighted average        (keys: xgb, lgb)
  • v2  — stacking ensemble                  (keys: base_models, meta_model)
  • v3  — stacking + isotonic calibration    (keys: base_models, meta_model, calibrator)

Callers always use the same API:
    model.predict(features_dict) -> {risk_score, risk_level, confidence, ...}

Design decisions (Phase 1 & 3)
-------------------------------
* The artifact's tuned `threshold` is the SINGLE source of truth for every risk
  level and alert cutoff. Nothing in the router hardcodes 0.45/0.70.
* Missing inputs are NEVER silently treated as normal. Key clinical inputs are
  tracked and reported in `missing_features`; `confidence` drops accordingly.
* `explain()` returns real SHAP contributions for the xgb base estimator — no
  hand-waved "feature importance" numbers.
"""
import joblib
import numpy as np
from pathlib import Path
from functools import lru_cache

from ..config import get_settings

# Key bedside inputs whose absence should reduce confidence. Maps the clinical
# label to the raw and engineered feature keys that can carry its value.
KEY_INPUTS = {
    "lactate":    ("Lactate", "Lactate_last"),
    "MAP":        ("MAP", "MAP_last"),
    "HR":         ("HR", "HR_last"),
    "RR":         ("RESP", "RESP_last", "Resp", "Resp_last"),
    "temperature": ("TEMP", "TEMP_last", "Temp", "Temp_last"),
    "WBC":        ("WBC", "WBC_last"),
    "creatinine": ("Creatinine", "Creatinine_last"),
}


def score_to_level(score: float, threshold: float) -> str:
    """
    Map a probability to a clinical risk level using the model's tuned alert
    threshold. Below the threshold = low; the [threshold, 1] band is split into
    medium / high / critical thirds.
    """
    if score < threshold:
        return "low"
    span = max(1.0 - threshold, 1e-6)
    frac = (score - threshold) / span
    if frac < 0.34:
        return "medium"
    if frac < 0.67:
        return "high"
    return "critical"


def alert_thresholds_from(threshold: float) -> dict[str, float]:
    """Derive the three alert cutoffs from the tuned threshold (one source)."""
    span = max(1.0 - threshold, 1e-6)
    return {
        "medium":   round(threshold, 4),
        "high":     round(threshold + span / 3.0, 4),
        "critical": round(threshold + 2.0 * span / 3.0, 4),
    }


def feature_label(name: str) -> str:
    """Turn an engineered feature name into something a clinician can read."""
    base = name
    for suffix in ("_last", "_mean", "_max", "_min", "_std", "_range", "_trend", "_pos_in_range"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    custom = {
        "sirs_count": "SIRS criteria", "sofa_total_proxy": "SOFA proxy",
        "shock_index": "Shock index", "lactate_x_wbc": "Lactate × WBC",
        "lactate_x_hr": "Lactate × HR", "flag_high_lactate": "High lactate",
        "flag_hypotension": "Hypotension", "flag_tachycardia": "Tachycardia",
        "flag_tachypnea": "Tachypnea", "flag_hypoxia": "Hypoxia",
        "flag_high_wbc": "High WBC", "flag_aki": "Acute kidney injury",
    }
    return custom.get(name, base)


class SepNovaModel:
    def __init__(self, model_path: str):
        self._artifact = joblib.load(model_path)
        self.version       = self._artifact.get("version", "v1.0")
        self.feature_names: list[str] = self._artifact["feature_names"]
        self.threshold     = float(self._artifact.get("threshold", 0.40))

        # v2 / v3 stacking
        self._base_models = self._artifact.get("base_models")     # list[(name, model)]
        self._meta_model  = self._artifact.get("meta_model")
        self._calibrator  = self._artifact.get("calibrator")      # v3 only

        # v1 backward compat
        self.xgb = self._artifact.get("xgb")
        self.lgb = self._artifact.get("lgb")
        if self.xgb is None and self._base_models:
            bm = dict(self._base_models)
            self.xgb = bm.get("xgb")
            self.lgb = bm.get("lgb")

        self._explainer = None   # lazily built SHAP TreeExplainer

    @property
    def is_stacked(self) -> bool:
        return bool(self._base_models) and (self._meta_model is not None or self._calibrator is not None)

    @property
    def trained_at(self):
        return self._artifact.get("trained_at")

    @property
    def alert_thresholds(self) -> dict[str, float]:
        return alert_thresholds_from(self.threshold)

    def _featurise(self, features: dict):
        """1-row DataFrame with the exact training column names."""
        import pandas as pd
        row = {}
        for f in self.feature_names:
            v = features.get(f, 0.0)
            try:
                row[f] = float(v) if v is not None else 0.0
            except (TypeError, ValueError):
                row[f] = 0.0
        return pd.DataFrame([row])

    def _missing_key_inputs(self, features: dict) -> list[str]:
        """Clinical inputs that are absent (or zero) in the supplied feature dict."""
        missing = []
        for label, keys in KEY_INPUTS.items():
            present = False
            for k in keys:
                try:
                    if features.get(k) is not None and float(features.get(k)) > 0:
                        present = True
                        break
                except (TypeError, ValueError):
                    continue
            if not present:
                missing.append(label)
        return missing

    def predict(self, features: dict) -> dict:
        """Score a single patient. features = {feature_name: value, ...}."""
        x = self._featurise(features)
        xgb_score = lgb_score = 0.0

        if self.is_stacked:
            import pandas as pd
            names = [n for n, _ in self._base_models]
            probs = [float(m.predict_proba(x)[0, 1]) for _, m in self._base_models]
            base_probs = pd.DataFrame([probs], columns=names)
            bp = dict(zip(names, probs))
            xgb_score, lgb_score = bp.get("xgb", 0.0), bp.get("lgb", 0.0)
            if self._calibrator is not None:          # v3: base -> meta -> isotonic
                score = float(self._calibrator.predict_proba(base_probs)[0, 1])
            else:                                     # v2: base -> meta
                score = float(self._meta_model.predict_proba(base_probs)[0, 1])
        elif self.xgb is not None and self.lgb is not None:
            xgb_score = float(self.xgb.predict_proba(x)[0, 1])
            lgb_score = float(self.lgb.predict_proba(x)[0, 1])
            score = 0.55 * xgb_score + 0.45 * lgb_score
        else:
            raise RuntimeError("Model artifact has no usable estimator.")

        missing = self._missing_key_inputs(features)
        # Report but do not hide imputation: every absent model column is filled
        # with 0.0 (the training missing-value sentinel).
        imputed = sum(
            1 for f in self.feature_names
            if features.get(f) is None or features.get(f) == 0
        )
        confidence = round(max(0.30, 1.0 - 0.12 * len(missing)), 2)

        return {
            "risk_score":       round(score, 4),
            "risk_level":       score_to_level(score, self.threshold),
            "xgb_score":        round(xgb_score, 4),
            "lgb_score":        round(lgb_score, 4),
            "model_version":    self.version,
            "confidence":       confidence,
            "data_complete":    len(missing) == 0,
            "missing_features": missing,
            "imputed_features": int(imputed),
        }

    def explain(self, features: dict, top_k: int = 5) -> list[dict]:
        """
        Per-prediction SHAP values for the top contributing features.
        Uses the xgb base estimator in the shared engineered feature space.
        """
        import shap

        x = self._featurise(features)
        if self.xgb is None:
            raise RuntimeError("Artifact has no xgb base estimator to explain.")
        if self._explainer is None:
            self._explainer = shap.TreeExplainer(self.xgb)

        values = self._explainer.shap_values(x)
        if isinstance(values, list):                    # some xgboost versions
            values = values[1] if len(values) > 1 else values[0]
        arr = np.asarray(values, dtype=float)
        if arr.ndim == 3:                               # (rows, features, classes)
            arr = arr[0, :, -1]
        elif arr.ndim == 2:
            arr = arr[0]

        order = np.argsort(np.abs(arr))[::-1][:top_k]
        out = []
        for idx in order:
            name = self.feature_names[int(idx)]
            out.append({
                "feature": name,
                "label":   feature_label(name),
                "value":   float(x.iloc[0, int(idx)]),
                "shap":    round(float(arr[int(idx)]), 5),
            })
        return out

    def predict_batch(self, features_list: list[dict]) -> list[dict]:
        return [self.predict(f) for f in features_list]

    def get_metrics(self) -> dict:
        return self._artifact.get("metrics", {})


@lru_cache()
def get_model() -> SepNovaModel:
    path = Path(get_settings().model_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Model artifact not found at {path}. "
            "Trained scores are unavailable — no fabricated score will be returned.\n"
            "  Train it first:  cd backend && python ml/train_v3.py"
        )
    return SepNovaModel(str(path))
