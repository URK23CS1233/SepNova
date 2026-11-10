"""
SepNova — Shared Feature Engineering (SINGLE SOURCE OF TRUTH)
============================================================
Both the training pipeline (build_dataset_v3.py / train_v3.py) and the live
inference API (app/routers/insights.py) import from THIS module. Keeping ONE
implementation guarantees train/inference feature parity — historically the
single most common source of production ML bugs.

Pipeline:
    readings ──compute_base_stats──▶ base stats dict (26 params × 6 stats)
    base stats + Age/Gender/HospAdmTime ──build_feature_vector──▶ full feature dict

IMPORTANT — missing-value handling:
    A parameter with no readings yields 0.0 for all its stats (the model treats
    0.0 as "missing"). Every "less-than" clinical threshold flag is therefore
    GUARDED with a presence check (value > 0) so a missing 0.0 is never mistaken
    for a pathologically low value. This must be identical at train and inference.
"""
from __future__ import annotations

# 26 clinical parameters. These names match BOTH the step2/step3 column prefixes
# AND the `parameter` values stored in the patient_readings table.
PARAMETERS = [
    "HR", "O2SAT", "TEMP", "SBP", "MAP", "DBP", "RESP",
    "Lactate", "WBC", "Creatinine", "Bilirubin_total",
    "Platelets", "Glucose", "Hgb", "pH", "PaCO2", "HCO3",
    "BUN", "Calcium", "PTT", "TroponinI", "AST",
    "Bilirubin_direct", "BaseExcess", "Hct", "Potassium",
]
STATS = ["mean", "std", "min", "max", "last", "range"]
EXTRA_COLS = ["Age", "Gender", "HospAdmTime"]


def _f(v, default: float = 0.0) -> float:
    """Coerce to float, falling back to default on None / bad values."""
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _g(stats: dict, key: str) -> float:
    return _f(stats.get(key, 0.0))


# ── 1. Base rolling statistics ────────────────────────────────────────────────

def compute_base_stats(readings, parameters=PARAMETERS) -> dict:
    """
    Aggregate a chronologically-ordered list of {parameter, value} readings into
    rolling stats. Returns {f"{param}_{stat}": float} for every param × stat.

    `readings` MUST be ordered oldest→newest so that `_last` is the most recent
    value. Params with no readings get 0.0 for all six stats.
    """
    import numpy as np

    grouped: dict[str, list] = {p: [] for p in parameters}
    for r in readings or []:
        p = r.get("parameter")
        v = r.get("value", r.get("value_numeric"))
        if p in grouped and v is not None:
            try:
                grouped[p].append(float(v))
            except (TypeError, ValueError):
                continue

    stats: dict[str, float] = {}
    for p in parameters:
        vals = grouped[p]
        if vals:
            arr = np.asarray(vals, dtype=np.float64)
            stats[f"{p}_mean"]  = float(arr.mean())
            stats[f"{p}_std"]   = float(arr.std()) if len(arr) > 1 else 0.0
            stats[f"{p}_min"]   = float(arr.min())
            stats[f"{p}_max"]   = float(arr.max())
            stats[f"{p}_last"]  = float(arr[-1])
            stats[f"{p}_range"] = float(arr.max() - arr.min())
        else:
            for s in STATS:
                stats[f"{p}_{s}"] = 0.0
    return stats


# ── 2. Clinical threshold flags (Sepsis-3 / ICU norms) ────────────────────────

def apply_clinical_flags(stats: dict) -> dict:
    """Binary abnormality flags + SIRS count. Less-than flags are presence-guarded."""
    s = dict(stats)

    hr    = _g(s, "HR_last")
    mapl  = _g(s, "MAP_last")
    temp  = _g(s, "TEMP_last")
    o2    = _g(s, "O2SAT_last")
    resp  = _g(s, "RESP_last")
    wbc   = _g(s, "WBC_last")
    lact  = _g(s, "Lactate_last")
    creat = _g(s, "Creatinine_last")
    plt   = _g(s, "Platelets_last")
    ph    = _g(s, "pH_last")
    bili  = _g(s, "Bilirubin_total_last")
    ptt   = _g(s, "PTT_last")
    trop  = _g(s, "TroponinI_last")
    bun   = _g(s, "BUN_last")

    def lt(v: float, thr: float) -> float:   # guarded: missing (0.0) never flags
        return 1.0 if (v > 0.0 and v < thr) else 0.0

    def gt(v: float, thr: float) -> float:
        return 1.0 if v > thr else 0.0

    s["flag_tachycardia"]      = gt(hr, 100)
    s["flag_bradycardia"]      = lt(hr, 60)
    s["flag_hypotension"]      = lt(mapl, 65)
    s["flag_tachypnea"]        = gt(resp, 22)
    s["flag_fever"]            = gt(temp, 38.3)
    s["flag_hypothermia"]      = lt(temp, 36.0)
    s["flag_hypoxia"]          = lt(o2, 94)
    s["flag_high_lactate"]     = gt(lact, 2.0)
    s["flag_very_hi_lactate"]  = gt(lact, 4.0)
    s["flag_high_wbc"]         = gt(wbc, 12)
    s["flag_low_wbc"]          = lt(wbc, 4)
    s["flag_aki"]              = gt(creat, 1.5)
    s["flag_severe_aki"]       = gt(creat, 3.0)
    s["flag_thrombocytopenia"] = lt(plt, 100)
    s["flag_low_plt_severe"]   = lt(plt, 50)
    s["flag_acidosis"]         = lt(ph, 7.35)
    s["flag_severe_acidosis"]  = lt(ph, 7.25)
    s["flag_elevated_bili"]    = gt(bili, 2.0)
    s["flag_elevated_ptt"]     = gt(ptt, 40)
    s["flag_elevated_trop"]    = gt(trop, 0.04)
    s["flag_elevated_bun"]     = gt(bun, 25)

    # SIRS criteria count (≥2 = SIRS): temp, HR, RESP, WBC
    s["sirs_count"] = min(
        s["flag_fever"] + s["flag_hypothermia"] +
        s["flag_tachycardia"] + s["flag_tachypnea"] +
        s["flag_high_wbc"] + s["flag_low_wbc"],
        4.0,
    )
    s["sepsis_screen_score"] = s["sirs_count"] + s["flag_high_lactate"] * 2.0
    return s


# ── 3. Trend proxies  (last − mean) / (std + ε) ───────────────────────────────

# (param, higher_is_worse). Sign is normalised so positive == deteriorating.
TREND_PARAMS = [
    ("HR", True), ("RESP", True), ("Lactate", True), ("Creatinine", True),
    ("WBC", True), ("BUN", True),
    ("O2SAT", False), ("MAP", False), ("SBP", False), ("pH", False),
    ("Platelets", False), ("Hgb", False),
]


def apply_trends(stats: dict) -> dict:
    s = dict(stats)
    for feat, higher_worse in TREND_PARAMS:
        mu   = _g(s, f"{feat}_mean")
        std  = _g(s, f"{feat}_std")
        last = _g(s, f"{feat}_last")
        z = (last - mu) / (std + 0.001)
        s[f"{feat}_trend"] = z if higher_worse else -z
    return s


# ── 4. Interactions, ratios, SOFA/qSOFA proxies, range position ───────────────

def _safe_div(a: float, b: float, fill: float = 0.0) -> float:
    return a / b if b != 0 else fill


def apply_interactions(stats: dict) -> dict:
    s = dict(stats)
    g = lambda k: _g(s, k)

    # Shock index & interaction terms
    s["shock_index"]          = _safe_div(g("HR_last"), g("SBP_last") + 1.0)
    s["shock_index_mean"]     = _safe_div(g("HR_mean"), g("SBP_mean") + 1.0)
    s["lactate_x_wbc"]        = g("Lactate_last") * g("WBC_last")
    s["lactate_x_hr"]         = g("Lactate_last") * g("HR_last")
    s["map_x_creatinine"]     = g("MAP_last") * g("Creatinine_last")
    s["bun_creatinine_ratio"] = _safe_div(g("BUN_last"), g("Creatinine_last") + 0.001)
    s["map_x_platelets"]      = g("MAP_last") * g("Platelets_last")
    s["resp_x_paco2"]         = g("RESP_last") * g("PaCO2_last")
    s["hco3_x_ph"]            = g("HCO3_last") * g("pH_last")
    s["creat_range_ratio"]    = _safe_div(g("Creatinine_range"), g("Creatinine_mean") + 0.001)
    s["lactate_range_ratio"]  = _safe_div(g("Lactate_range"), g("Lactate_mean") + 0.001)
    s["hr_variability"]       = _safe_div(g("HR_std"), g("HR_mean") + 0.001)
    s["bp_variability"]       = _safe_div(g("SBP_std"), g("SBP_mean") + 0.001)

    # SOFA component proxies (presence-guarded for "low is bad" organs)
    o2 = g("O2SAT_last")
    s["sofa_resp_proxy"]  = min(max(100.0 - o2, 0.0), 10.0) if o2 > 0 else 0.0
    plt = g("Platelets_last")
    s["sofa_coag_proxy"]  = (4.0 if 0 < plt < 50 else 3.0 if 0 < plt < 100
                             else 1.0 if 0 < plt < 150 else 0.0)
    bili = g("Bilirubin_total_last")
    s["sofa_liver_proxy"] = (4.0 if bili > 12 else 3.0 if bili > 6
                             else 2.0 if bili > 2 else 1.0 if bili > 1.2 else 0.0)
    creat = g("Creatinine_last")
    s["sofa_renal_proxy"] = (4.0 if creat > 5 else 3.0 if creat > 3.5
                             else 2.0 if creat > 2 else 1.0 if creat > 1.2 else 0.0)
    mapl = g("MAP_last")
    s["sofa_cardio_proxy"] = 1.0 if 0 < mapl < 70 else 0.0
    s["sofa_total_proxy"]  = (s["sofa_resp_proxy"] + s["sofa_coag_proxy"] +
                              s["sofa_liver_proxy"] + s["sofa_renal_proxy"] +
                              s["sofa_cardio_proxy"])

    # qSOFA proxies
    s["qsofa_resp_flag"]   = 1.0 if g("RESP_last") >= 22 else 0.0
    sbp = g("SBP_last")
    s["qsofa_sbp_flag"]    = 1.0 if 0 < sbp <= 100 else 0.0
    s["qsofa_total_proxy"] = s["qsofa_resp_flag"] + s["qsofa_sbp_flag"]

    # Range position: is "last" near the worst extreme of the window?
    for col in ["HR", "MAP", "Lactate", "Creatinine", "O2SAT", "WBC", "Platelets"]:
        mn = g(f"{col}_min"); mx = g(f"{col}_max"); last = g(f"{col}_last")
        s[f"{col}_pos_in_range"] = _safe_div(last - mn, (mx - mn) + 1e-4)

    return s


# ── 5. Full pipeline ──────────────────────────────────────────────────────────

def build_feature_vector(stats: dict) -> dict:
    """
    Run all engineering steps. `stats` must contain the base param stats PLUS
    Age / Gender / HospAdmTime (passed through unchanged). Returns the complete
    engineered feature dict the model consumes. Deterministic key order.
    """
    return apply_interactions(apply_trends(apply_clinical_flags(stats)))


def feature_names_from(stats: dict) -> list[str]:
    """Canonical ordered feature-name list produced by build_feature_vector(stats)."""
    return list(build_feature_vector(stats).keys())
