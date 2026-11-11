"""In-memory demo data served when running in demo mode (Bearer demo).

Used so the dashboard/alerts/patient pages show realistic content even when
Supabase credentials are unavailable.
"""
from datetime import datetime, timezone, timedelta
import uuid

NOW = datetime.now(timezone.utc)

PATIENTS = [
    {"patient_id": "P-1001", "age": 68, "gender": 1, "hosp_adm_time": 12.0, "icu_los": 3, "ward": "ICU-A", "status": "active"},
    {"patient_id": "P-1002", "age": 54, "gender": 0, "hosp_adm_time": 24.0, "icu_los": 5, "ward": "ICU-A", "status": "active"},
    {"patient_id": "P-1003", "age": 72, "gender": 1, "hosp_adm_time": 6.0,  "icu_los": 2, "ward": "ICU-A", "status": "active"},
    {"patient_id": "P-1004", "age": 45, "gender": 0, "hosp_adm_time": 48.0, "icu_los": 7, "ward": "ICU-B", "status": "active"},
    {"patient_id": "P-1005", "age": 61, "gender": 1, "hosp_adm_time": 8.0,  "icu_los": 1, "ward": "ICU-B", "status": "active"},
    {"patient_id": "P-1006", "age": 79, "gender": 0, "hosp_adm_time": 36.0, "icu_los": 4, "ward": "ICU-B", "status": "active"},
    {"patient_id": "P-1007", "age": 33, "gender": 1, "hosp_adm_time": 10.0, "icu_los": 2, "ward": "ICU-C", "status": "active"},
    {"patient_id": "P-1008", "age": 58, "gender": 0, "hosp_adm_time": 20.0, "icu_los": 3, "ward": "ICU-C", "status": "active"},
]

RISK = {
    "P-1001": (0.87, "critical"),
    "P-1002": (0.62, "high"),
    "P-1003": (0.74, "critical"),
    "P-1004": (0.31, "medium"),
    "P-1005": (0.18, "low"),
    "P-1006": (0.55, "high"),
    "P-1007": (0.09, "low"),
    "P-1008": (0.42, "medium"),
}

VITALS = {
    "P-1001": {"hour": 24, "hr": 118, "o2sat": 91, "temp": 38.6, "sbp": 92, "map": 64, "dbp": 58, "resp": 26},
    "P-1002": {"hour": 24, "hr": 102, "o2sat": 94, "temp": 38.1, "sbp": 108, "map": 76, "dbp": 68, "resp": 22},
    "P-1003": {"hour": 24, "hr": 124, "o2sat": 89, "temp": 39.0, "sbp": 88, "map": 60, "dbp": 54, "resp": 28},
    "P-1004": {"hour": 24, "hr": 88,  "o2sat": 97, "temp": 37.2, "sbp": 122, "map": 86, "dbp": 74, "resp": 18},
    "P-1005": {"hour": 24, "hr": 76,  "o2sat": 98, "temp": 36.8, "sbp": 118, "map": 82, "dbp": 70, "resp": 16},
    "P-1006": {"hour": 24, "hr": 96,  "o2sat": 93, "temp": 37.9, "sbp": 104, "map": 72, "dbp": 62, "resp": 21},
    "P-1007": {"hour": 24, "hr": 72,  "o2sat": 99, "temp": 36.6, "sbp": 120, "map": 84, "dbp": 72, "resp": 14},
    "P-1008": {"hour": 24, "hr": 90,  "o2sat": 95, "temp": 37.5, "sbp": 112, "map": 78, "dbp": 66, "resp": 19},
}


def _patient_out(p):
    pid = p["patient_id"]
    score, level = RISK[pid]
    return {
        "id": str(uuid.uuid4()),
        "patient_id": pid,
        "age": p["age"],
        "gender": p["gender"],
        "hosp_adm_time": p["hosp_adm_time"],
        "icu_los": p["icu_los"],
        "ward": p["ward"],
        "status": p["status"],
        "created_at": (NOW - timedelta(days=1)).isoformat(),
        "latest_risk_score": score,
        "latest_risk_level": level,
        "latest_vitals": VITALS[pid],
    }


def list_patients(ward=None, status="active", limit=100):
    out = []
    for p in PATIENTS:
        if status and p["status"] != status:
            continue
        if ward and p["ward"] != ward:
            continue
        out.append(_patient_out(p))
        if len(out) >= limit:
            break
    return out


def get_patient(patient_id):
    for p in PATIENTS:
        if p["patient_id"] == patient_id:
            return _patient_out(p)
    return None


def dashboard_summary():
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for pid, (score, level) in RISK.items():
        if level in counts:
            counts[level] += 1
    return {
        "total_patients": len(PATIENTS),
        "critical_count": counts["critical"],
        "high_risk_count": counts["high"],
        "medium_risk_count": counts["medium"],
        "low_risk_count": counts["low"],
        "unacknowledged_alerts": 3,
        "latest_model_auroc": 0.912,
    }


def get_vitals(patient_id):
    v = VITALS.get(patient_id)
    if not v:
        return []
    # return a small trajectory
    traj = []
    for h in range(0, 25, 3):
        traj.append({"id": str(uuid.uuid4()), "patient_id": patient_id, "recorded_at": (NOW - timedelta(hours=24-h)).isoformat(), "hour": h, **{k: v[k] for k in ("hr","o2sat","temp","sbp","map","dbp","resp")}})
    return traj


def get_labs(patient_id):
    return [{
        "id": str(uuid.uuid4()), "patient_id": patient_id, "hour": 24, "recorded_at": NOW.isoformat(),
        "lactate": 2.4, "wbc": 14.2, "creatinine": 1.3, "bilirubin_total": 1.1,
        "platelets": 180, "glucose": 142, "hgb": 11.2, "hct": 33.1, "potassium": 4.1,
        "ph": 7.32, "paco2": 38, "hco3": 22, "base_excess": -3, "ptt": 32,
        "bun": 24, "calcium": 8.6,
    }]


def get_predictions(patient_id):
    score, level = RISK.get(patient_id, (0.1, "low"))
    return [{
        "patient_id": patient_id,
        "risk_score": score,
        "risk_level": level,
        "xgb_score": score - 0.02,
        "lgb_score": score + 0.01,
        "model_version": "v3.0",
        "predicted_at": (NOW - timedelta(minutes=15)).isoformat(),
        "confidence": 0.85,
        "data_complete": True,
        "missing_features": [],
        "imputed_features": 0,
        "top_features": [{"feature": "HR_mean", "shap": 0.42}, {"feature": "Lactate_last", "shap": 0.31}],
        "explanation_method": "shap",
        "alert_thresholds": {"critical": 0.7, "high": 0.5, "medium": 0.3},
    }]


ALERTS = [
    {"id": str(uuid.uuid4()), "patient_id": "P-1001", "alert_type": "sepsis_risk", "severity": "critical",
     "message": "High sepsis risk detected (score 0.87). Review immediately.", "risk_score": 0.87,
     "is_acknowledged": False, "created_at": (NOW - timedelta(minutes=5)).isoformat()},
    {"id": str(uuid.uuid4()), "patient_id": "P-1003", "alert_type": "sepsis_risk", "severity": "critical",
     "message": "High sepsis risk detected (score 0.74). Review immediately.", "risk_score": 0.74,
     "is_acknowledged": False, "created_at": (NOW - timedelta(minutes=12)).isoformat()},
    {"id": str(uuid.uuid4()), "patient_id": "P-1002", "alert_type": "sepsis_risk", "severity": "high",
     "message": "Elevated sepsis risk (score 0.62). Monitor closely.", "risk_score": 0.62,
     "is_acknowledged": False, "created_at": (NOW - timedelta(minutes=30)).isoformat()},
    {"id": str(uuid.uuid4()), "patient_id": "P-1006", "alert_type": "sepsis_risk", "severity": "high",
     "message": "Elevated sepsis risk (score 0.55). Monitor closely.", "risk_score": 0.55,
     "is_acknowledged": True, "created_at": (NOW - timedelta(hours=2)).isoformat()},
]


def list_alerts(acknowledged=False, severity=None, limit=50):
    out = [a for a in ALERTS if a["is_acknowledged"] == acknowledged]
    if severity:
        out = [a for a in out if a["severity"] == severity]
    return out[:limit]


def alert_stats():
    total = len(ALERTS)
    unacked = sum(1 for a in ALERTS if not a["is_acknowledged"])
    crit = sum(1 for a in ALERTS if a["severity"] == "critical" and not a["is_acknowledged"])
    return {"total": total, "unacknowledged": unacked, "critical_unacked": crit}
