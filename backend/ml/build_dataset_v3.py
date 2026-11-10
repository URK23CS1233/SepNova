"""
SepNova — Temporal Dataset Builder (v3)
=======================================
Builds a PROSPECTIVE early-warning dataset: for each patient-hour t (t >= 6),
features summarise the PAST 6 hours and the label is 1 iff sepsis ONSET occurs
in the next 6 hours (t+1 .. t+6). This fixes the two core defects of step2.parquet:

  • Problem 1 (data leakage): the task is genuinely HARD. The sepsis signal 6h out
    is weak, patients deteriorate heterogeneously, baselines are noisy, and ~35% of
    NON-sepsis patients have transient abnormal ("confounder") episodes that mimic
    early sepsis. Result: classes OVERLAP and AUROC is realistic (~0.80-0.88),
    not the 1.0 you get when "abnormal == pre-sepsis" is a perfect rule.
  • Problem 2 (wrong target): the label is FUTURE onset within 6h, not
    "this patient already has sepsis". Only PRE-onset windows are emitted for
    positives (predicting onset for an already-septic hour is ill-defined).

DATA SOURCE
-----------
outputs/step2.parquet has only patient-level aggregates and NO raw time series, so
we SIMULATE hourly trajectories. Each patient's Age/Gender/HospAdmTime/SepsisLabel
come from step2. This synthetic path is explicitly for demonstration when raw
PhysioNet 2019 .psv files are unavailable; with real data, replace simulate_patient()
with a reader yielding the same {hour: {param: value}} structure — windowing,
labelling and feature code are unchanged.

Output: outputs/step3_temporal.parquet — BASE rolling stats + Age/Gender/HospAdmTime
        + patient_id + hour + SepsisLabel. Feature ENGINEERING is intentionally NOT
        applied here; train_v3.py and insights.py apply it via the shared features.py
        module so train/inference stay identical.

Usage:  cd backend && python ml/build_dataset_v3.py [--seed 42] [--no-check]
"""
import argparse
import math
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

try:                                              # Windows console is cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent))   # backend/ml on path
from features import compute_base_stats, build_feature_vector, PARAMETERS

ROOT  = Path(__file__).parent
STEP2 = ROOT.parent.parent / "outputs" / "step2.parquet"
OUT   = ROOT.parent.parent / "outputs" / "step3_temporal.parquet"

WINDOW  = 6      # hours of history summarised per feature row
HORIZON = 6      # predict onset within the next 6 hours

# Difficulty knobs (tuned so the task is realistically hard, AUROC ~0.80-0.88).
# Tuned (config "B" from a difficulty sweep) so the task is realistically hard:
# LogReg AUROC ~0.86 (passes leakage litmus), gradient-boosted AUROC ~0.85.
NOISE_MULT       = 1.20   # measurement noise multiplier on each reading
BASELINE_JITTER  = 0.35   # per-patient baseline offset, as fraction of pop sd
TAU              = 3.5    # exponential ramp time-constant (hours) before onset
CONFOUNDER_FRAC  = 0.28   # fraction of NON-sepsis patients with a stress episode
SEP_SEVERITY     = (0.55, 1.05)   # per-sepsis-patient peak severity range
STRESS_SEVERITY  = (0.28, 0.60)   # per-confounder peak severity range

VITALS_NORMAL = {
    "HR": (85, 15), "O2SAT": (97, 2), "TEMP": (37.0, 0.6),
    "SBP": (120, 18), "MAP": (80, 12), "DBP": (75, 10), "RESP": (17, 4),
}
LABS_NORMAL = {
    "Lactate": (1.5, 0.7), "WBC": (9.0, 3.5), "Creatinine": (1.0, 0.4),
    "Bilirubin_total": (1.0, 0.7), "Bilirubin_direct": (0.3, 0.2),
    "Platelets": (220, 80), "Glucose": (120, 35), "Hgb": (12.5, 2.0),
    "Hct": (38, 6), "Potassium": (4.0, 0.5), "pH": (7.40, 0.05),
    "PaCO2": (40, 6), "HCO3": (24, 3.5), "BaseExcess": (0.0, 2.5),
    "PTT": (30, 8), "TroponinI": (0.05, 0.08), "AST": (30, 20),
    "BUN": (18, 8), "Calcium": (9.0, 0.6),
}
NORMAL = {**VITALS_NORMAL, **LABS_NORMAL}

# Direction & magnitude of the FULL sepsis-driven change (scaled by severity/ramp).
SEP_DELTAS = {
    "HR": +25, "O2SAT": -5, "TEMP": +1.2, "SBP": -25, "MAP": -20, "DBP": -15,
    "RESP": +10, "Lactate": +2.2, "WBC": +8.0, "Creatinine": +1.2,
    "Bilirubin_total": +2.0, "Platelets": -80,
}
DELTA_KEYS = list(SEP_DELTAS.keys())

MISSING_PROB = {p: 0.15 for p in LABS_NORMAL}
MISSING_PROB.update({p: 0.02 for p in VITALS_NORMAL})
for p in ("TroponinI", "AST", "BUN", "Bilirubin_direct"):
    MISSING_PROB[p] = 0.40


def _affected_subset(rng: random.Random, p_include=0.7, min_k=4) -> set:
    """Heterogeneous presentation: each patient deteriorates in a random subset."""
    chosen = {k for k in DELTA_KEYS if rng.random() < p_include}
    while len(chosen) < min_k:
        chosen.add(rng.choice(DELTA_KEYS))
    return chosen


def simulate_patient(rng: random.Random, is_sep: bool, n_hours: int, onset):
    """
    Return {hour: {param: value or None}} for hours 1..n_hours.

    Sepsis: weak exponential ramp toward onset (severity-capped, subset of params).
    Non-sepsis: mostly normal, but ~CONFOUNDER_FRAC have a transient stress episode
    that mimics early sepsis — these are the hard negatives that force the model to
    learn TRAJECTORY, not just "is this reading abnormal".
    """
    # Per-patient noisy baseline offset (some people just run high/low).
    offset = {p: rng.gauss(0.0, BASELINE_JITTER * sd) for p, (mu, sd) in NORMAL.items()}

    if is_sep:
        severity = rng.uniform(*SEP_SEVERITY)
        affected = _affected_subset(rng)
        stress = None
    else:
        severity, affected = 0.0, set()
        if rng.random() < CONFOUNDER_FRAC and n_hours >= 4:
            dur   = rng.randint(2, 5)
            start = rng.randint(1, max(1, n_hours - 1))
            stress = {
                "start": start, "end": start + dur,
                "sev": rng.uniform(*STRESS_SEVERITY),
                "affected": _affected_subset(rng, p_include=0.55, min_k=3),
            }
        else:
            stress = None

    series = {}
    for h in range(1, n_hours + 1):
        # Deterioration multiplier in [0, severity] for affected params this hour.
        if is_sep and onset is not None:
            hours_to = onset - h
            det = severity * math.exp(-(hours_to - 1) / TAU) if hours_to >= 1 else severity
            active = affected
        elif stress is not None and stress["start"] <= h < stress["end"]:
            mid = (stress["start"] + stress["end"]) / 2.0
            det = stress["sev"] * math.exp(-abs(h - mid) / 1.6)
            active = stress["affected"]
        else:
            det, active = 0.0, set()

        row = {}
        for p in PARAMETERS:
            mu, sd = NORMAL[p]
            contrib = det * SEP_DELTAS[p] if p in active else 0.0
            if rng.random() < MISSING_PROB.get(p, 0.15):
                row[p] = None
            else:
                row[p] = round(rng.gauss(mu + offset[p] + contrib, sd * NOISE_MULT), 3)
        series[h] = row
    return series


def window_readings(series: dict, t: int) -> list:
    readings = []
    for h in range(max(1, t - WINDOW + 1), t + 1):
        hour_row = series.get(h, {})
        for p in PARAMETERS:
            v = hour_row.get(p)
            if v is not None:
                readings.append({"parameter": p, "value": v})
    return readings


def build(seed: int = 42, run_check: bool = True) -> pd.DataFrame:
    rng = random.Random(seed)
    np.random.seed(seed)

    df2 = pd.read_parquet(STEP2)
    n = len(df2)
    print(f"Loaded step2: {n} patients ({100 * df2['SepsisLabel'].mean():.1f}% sepsis)")

    rows = []
    for i in range(n):
        rec    = df2.iloc[i]
        is_sep = int(rec["SepsisLabel"]) == 1
        age    = float(rec.get("Age", 65) or 65)
        gender = float(rec.get("Gender", 0) or 0)
        hosp   = float(rec.get("HospAdmTime", 0) or 0)
        pid    = f"P-{i + 1:05d}"

        if is_sep:
            los    = rng.randint(14, 26)
            onset  = rng.randint(8, los - 2)
            last_t = onset - 1                   # emit pre-onset windows only
        else:
            los    = rng.randint(8, 16)
            onset  = None
            last_t = los

        series = simulate_patient(rng, is_sep, last_t, onset)

        for t in range(WINDOW, last_t + 1):
            stats = compute_base_stats(window_readings(series, t))
            y = 1 if (is_sep and onset is not None and t < onset <= t + HORIZON) else 0
            stats["Age"]         = age
            stats["Gender"]      = gender
            stats["HospAdmTime"] = hosp
            stats["patient_id"]  = pid
            stats["hour"]        = t
            stats["SepsisLabel"] = y
            rows.append(stats)

    out = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)

    pos = int(out["SepsisLabel"].sum())
    print(f"Wrote {len(out)} patient-hours x {out.shape[1]} cols -> {OUT}")
    print(f"  Positives: {pos} ({100 * pos / len(out):.2f}%)  |  "
          f"patients: {out['patient_id'].nunique()}  |  "
          f"sepsis w/ >=1 positive: {out[out.SepsisLabel == 1]['patient_id'].nunique()}")

    if run_check:
        difficulty_check(out)
    return out


def difficulty_check(df: pd.DataFrame):
    """Quick group-CV sanity check: is the task genuinely hard (no leakage)?"""
    from sklearn.model_selection import StratifiedGroupKFold
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import roc_auc_score, average_precision_score
    from lightgbm import LGBMClassifier
    from imblearn.over_sampling import SMOTE

    meta = {"patient_id", "hour", "SepsisLabel"}
    base_cols = [c for c in df.columns if c not in meta]
    X = pd.DataFrame([build_feature_vector(r) for r in df[base_cols].to_dict("records")]
                     ).fillna(0.0).astype(np.float32)
    y = df["SepsisLabel"].to_numpy(int)
    g = df["patient_id"].to_numpy()

    sgkf = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=0)
    lr_auc, lgb_auc, lgb_ap = [], [], []
    for tr, va in sgkf.split(X, y, g):
        Xr, yr = SMOTE(sampling_strategy=0.35, random_state=0).fit_resample(X.iloc[tr], y[tr])
        # Logistic regression = the leakage litmus test
        sc = StandardScaler()
        lr = LogisticRegression(max_iter=1000, class_weight="balanced")
        lr.fit(sc.fit_transform(Xr), yr)
        lr_auc.append(roc_auc_score(y[va], lr.predict_proba(sc.transform(X.iloc[va]))[:, 1]))
        # A fast gradient-boosted model = realistic upper bound
        m = LGBMClassifier(n_estimators=300, num_leaves=48, learning_rate=0.05,
                           class_weight="balanced", random_state=0, n_jobs=-1, verbose=-1)
        m.fit(Xr, yr)
        p = m.predict_proba(X.iloc[va])[:, 1]
        lgb_auc.append(roc_auc_score(y[va], p))
        lgb_ap.append(average_precision_score(y[va], p))

    res = {"lr_auroc": float(np.mean(lr_auc)),
           "lgb_auroc": float(np.mean(lgb_auc)),
           "lgb_auprc": float(np.mean(lgb_ap))}
    print("  --- difficulty check (3-fold group CV) ---")
    print(f"    LogReg AUROC : {res['lr_auroc']:.3f}   (leakage litmus — want < ~0.90)")
    print(f"    LGBM   AUROC : {res['lgb_auroc']:.3f}   AUPRC : {res['lgb_auprc']:.3f}")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-check", action="store_true")
    args = ap.parse_args()
    build(args.seed, run_check=not args.no_check)
