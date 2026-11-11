"""
SepNova — Synthetic ICU Sepsis Simulation Engine (SIMULATED DATA)
==================================================================
Generates an hourly ICU trajectory for a fictional patient with a configurable
sepsis onset hour, severity and measurement noise. For every hour it:

  1. Builds the same rolling 6-hour feature window used in training.
  2. Scores it with the trained artifact (no thresholds or scores are hardcoded).
  3. Computes SOFA, qSOFA and SIRS from the current window.
  4. Returns the top SHAP drivers for that hour.

All values are synthetic. This module never reads or writes patient data.
"""
from __future__ import annotations

import math

import numpy as np

from ml.features import compute_base_stats, build_feature_vector
from ml.sofa import compute_sofa, compute_qsofa

WINDOW_HOURS = 6

# Healthy ICU baseline and severe-sepsis target for each simulated parameter.
BASELINE = {
    "HR": 78.0, "MAP": 82.0, "RESP": 15.0, "TEMP": 36.9, "O2SAT": 98.0,
    "WBC": 7.5, "Lactate": 1.2, "Creatinine": 0.9, "Platelets": 240.0,
    "Bilirubin_total": 0.9,
}
SEPTIC = {
    "HR": 126.0, "MAP": 57.0, "RESP": 29.0, "TEMP": 38.9, "O2SAT": 89.0,
    "WBC": 19.5, "Lactate": 4.8, "Creatinine": 2.5, "Platelets": 82.0,
    "Bilirubin_total": 3.2,
}
NOISE_SD = {
    "HR": 4.0, "MAP": 4.0, "RESP": 2.0, "TEMP": 0.25, "O2SAT": 1.0,
    "WBC": 1.2, "Lactate": 0.25, "Creatinine": 0.15, "Platelets": 18.0,
    "Bilirubin_total": 0.20,
}
CLIP = {
    "HR": (30, 220), "MAP": (30, 140), "RESP": (5, 60), "TEMP": (33, 43),
    "O2SAT": (60, 100), "WBC": (0.5, 60), "Lactate": (0.2, 20),
    "Creatinine": (0.2, 12), "Platelets": (5, 600), "Bilirubin_total": (0.1, 30),
}

# Display metadata for the 12 requested simulation parameters.
DISPLAY = {
    "HR": ("Heart rate", "bpm"),
    "MAP": ("MAP", "mmHg"),
    "RESP": ("Resp rate", "bpm"),
    "TEMP": ("Temperature", "°C"),
    "O2SAT": ("SpO₂", "%"),
    "WBC": ("WBC", "K/µL"),
    "Lactate": ("Lactate", "mmol/L"),
    "Creatinine": ("Creatinine", "mg/dL"),
    "Platelets": ("Platelets", "K/µL"),
    "Bilirubin_total": ("Bilirubin", "mg/dL"),
    "GCS": ("GCS", "points"),
}


def _clip(name: str, value: float) -> float:
    lo, hi = CLIP.get(name, (float("-inf"), float("inf")))
    return float(min(max(value, lo), hi))


def _deterioration(hour: int, onset: int, severity: float, ramp_hours: int) -> float:
    """
    0 before the ramp begins, rising smoothly to 1 at onset, then held at 1.
    Severity scales how far toward the septic target the patient travels.
    """
    hours_to_onset = onset - hour
    if hours_to_onset >= ramp_hours:
        return 0.0
    if hours_to_onset >= 0:
        # Smooth S-curve over the ramp window.
        progress = 1.0 - (hours_to_onset / max(ramp_hours, 1))
        shaped = progress * progress * (3 - 2 * progress)
    else:
        shaped = 1.0
    return float(np.clip(shaped, 0.0, 1.0)) * severity


def _sofa_for(row: dict) -> dict:
    """SOFA from the current window. Room-air FiO2 is assumed."""
    return compute_sofa(
        pao2=None,
        fio2=0.21,
        spo2=row.get("O2SAT"),
        platelets=row.get("Platelets"),
        bilirubin=row.get("Bilirubin_total"),
        map_val=row.get("MAP"),
        creatinine=row.get("Creatinine"),
    )


def _sirs_for(row: dict) -> dict:
    """SIRS criteria count (standard bedside thresholds)."""
    temp = row.get("TEMP", 0) or 0
    hr = row.get("HR", 0) or 0
    resp = row.get("RESP", 0) or 0
    wbc = row.get("WBC", 0) or 0

    criteria = {
        "temperature": temp > 38.0 or (0 < temp < 36.0),
        "heart_rate": hr > 90,
        "resp_rate": resp > 20,
        "wbc": wbc > 12.0 or (0 < wbc < 4.0),
    }
    return {
        "sirs_count": int(sum(criteria.values())),
        "sirs_positive": sum(criteria.values()) >= 2,
        "criteria": criteria,
    }


def _top_features(model, features: dict) -> tuple[list[dict], str]:
    try:
        return model.explain(features, top_k=5), "shap"
    except Exception as e:
        return [], f"unavailable: {e}"


def run_simulation(
    model,
    onset_hour: int = 12,
    total_hours: int = 30,
    severity: float = 0.75,
    noise: float = 0.35,
    seed: int | None = 7,
    ramp_hours: int = 8,
) -> dict:
    """
    Replay a synthetic patient hour by hour and return the full trajectory.
    `model` is a loaded SepNovaModel (artifact-backed).
    """
    onset_hour = int(max(1, onset_hour))
    total_hours = int(max(onset_hour + 1, min(total_hours, 96)))
    severity = float(np.clip(severity, 0.0, 1.0))
    noise = float(np.clip(noise, 0.0, 1.0))
    ramp_hours = int(max(1, ramp_hours))

    rng = np.random.default_rng(seed)
    window: list[dict] = []
    hours: list[dict] = []
    first_flagged: int | None = None

    for hour in range(1, total_hours + 1):
        det = _deterioration(hour, onset_hour, severity, ramp_hours)

        row: dict[str, float] = {}
        for name, normal in BASELINE.items():
            target = SEPTIC[name]
            value = normal + det * (target - normal)
            value += rng.normal(0, NOISE_SD[name] * (0.4 + noise))
            row[name] = round(_clip(name, value), 2)

        # Derived bedside values not in the 12-parameter lab set.
        row["SBP"] = round(row["MAP"] * 1.35, 1)
        row["GCS"] = int(round(np.clip(15 - det * 4 + rng.normal(0, 0.4 * (0.4 + noise)), 3, 15)))

        window.append(row)
        window = window[-WINDOW_HOURS:]

        # Rolling feature window (same pipeline as live inference).
        readings = [
            {"parameter": name, "value": value}
            for past in window
            for name, value in past.items()
            if name != "GCS"          # GCS is monitored but not a model input
        ]
        stats = compute_base_stats(readings)
        stats["Age"] = 68.0
        stats["Gender"] = 1.0
        stats["HospAdmTime"] = -6.0
        features = build_feature_vector(stats)

        result = model.predict(features)
        sofa = _sofa_for(row)
        qsofa = compute_qsofa(resp_rate=row["RESP"], sbp=row["SBP"], gcs=row["GCS"])
        sirs = _sirs_for(row)
        top, method = _top_features(model, features)

        if first_flagged is None and result["risk_score"] >= model.threshold:
            first_flagged = hour

        vitals = {name: row[name] for name in ("HR", "MAP", "RESP", "TEMP", "O2SAT", "SBP", "GCS")}
        labs = {name: row[name] for name in ("WBC", "Lactate", "Creatinine", "Platelets", "Bilirubin_total")}

        hours.append({
            "hour": hour,
            "simulated": True,
            "pre_onset": hour < onset_hour,
            "vitals": vitals,
            "labs": labs,
            "vitals_display": [
                {"key": k, "label": DISPLAY[k][0], "unit": DISPLAY[k][1], "value": vitals[k]}
                for k in ("HR", "MAP", "RESP", "TEMP", "O2SAT", "GCS")
            ],
            "sofa": sofa,
            "qsofa": qsofa,
            "sirs": sirs,
            "risk_score": result["risk_score"],
            "risk_level": result["risk_level"],
            "xgb_score": result["xgb_score"],
            "lgb_score": result["lgb_score"],
            "model_version": result["model_version"],
            "confidence": result["confidence"],
            "data_complete": result["data_complete"],
            "missing_features": result["missing_features"],
            "top_features": top,
            "explanation_method": method,
        })

    lead_time = (onset_hour - first_flagged) if first_flagged is not None else None

    return {
        "simulated": True,
        "disclaimer": (
            "SIMULATED DATA — synthetic trajectory for demonstration and training only. "
            "Not a real patient. Decision support, not diagnosis."
        ),
        "config": {
            "onset_hour": onset_hour,
            "total_hours": total_hours,
            "severity": severity,
            "noise": noise,
            "seed": seed,
            "ramp_hours": ramp_hours,
            "window_hours": WINDOW_HOURS,
        },
        "model_version": model.version,
        "threshold": model.threshold,
        "alert_thresholds": model.alert_thresholds,
        "onset_hour": onset_hour,
        "first_flagged_hour": first_flagged,
        "lead_time_hours": lead_time,
        "lead_time_available": lead_time is not None,
        "hours": hours,
    }
