"""
SepNova — Synthetic Training Data Generator
===========================================
Produces `outputs/step2.parquet`: a patient-level, aggregated feature table whose
columns EXACTLY match what the inference path (app/ml_utils.build_patient_features)
produces. This guarantees the trained model's `feature_names` line up with the
features predict.py feeds it at scoring time.

Why this exists: README/train.py reference `outputs/step2.parquet`, the output of a
PhysioNet-2019 preprocessing pipeline that is NOT included in this repo. This script
lets you train end-to-end locally without downloading the real challenge dataset.
(For real data, replace this with your own PhysioNet aggregation that emits the same
column names.)

Usage:
    cd SepNova
    pip install numpy pandas pyarrow
    python scripts/generate_training_data.py --n-patients 2000
"""
import argparse
import random
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).parent.parent / "outputs" / "step2.parquet"
OUT.parent.mkdir(parents=True, exist_ok=True)

# ── Distributions (mirror scripts/seed_data.py so train & demo data agree) ────
VITALS_NORMAL = {
    "hr": (85, 15), "o2sat": (97, 2), "temp": (37.0, 0.6),
    "sbp": (120, 18), "map": (80, 12), "dbp": (75, 10), "resp": (17, 4),
}
LABS_NORMAL = {
    "lactate": (1.5, 0.7), "wbc": (9.0, 3.5), "creatinine": (1.0, 0.4),
    "bilirubin_total": (1.0, 0.7), "bilirubin_direct": (0.3, 0.2),
    "platelets": (220, 80), "glucose": (120, 35), "hgb": (12.5, 2.0),
    "hct": (38, 6), "potassium": (4.0, 0.5), "ph": (7.40, 0.05),
    "paco2": (40, 6), "hco3": (24, 3.5), "base_excess": (0.0, 2.5),
    "ptt": (30, 8), "troponin_i": (0.05, 0.08), "ast": (30, 20),
    "bun": (18, 8), "calcium": (9.0, 0.6),
}
SEP_DELTAS = {
    "hr": +25, "o2sat": -5, "temp": +1.2, "sbp": -25, "map": -20,
    "dbp": -15, "resp": +10, "lactate": +2.2, "wbc": +8.0,
    "creatinine": +1.2, "bilirubin_total": +2.0, "platelets": -80,
}

# ── Feature-name maps — MUST match app/ml_utils.build_patient_features ────────
VITAL_NAME = {c: c.upper() for c in VITALS_NORMAL}   # hr -> HR, o2sat -> O2SAT, ...
LAB_NAME = {
    "lactate": "Lactate", "wbc": "WBC", "creatinine": "Creatinine",
    "bilirubin_total": "Bilirubin_total", "bilirubin_direct": "Bilirubin_direct",
    "platelets": "Platelets", "glucose": "Glucose", "hgb": "Hgb",
    "hct": "Hct", "potassium": "Potassium", "ph": "pH",
    "paco2": "PaCO2", "hco3": "HCO3", "base_excess": "BaseExcess",
    "ptt": "PTT", "troponin_i": "TroponinI", "ast": "AST",
    "bun": "BUN", "calcium": "Calcium",
}
SUFFIXES = ["mean", "std", "min", "max", "last", "range"]


def agg(values: list) -> dict:
    """Same six stats as build_patient_features._agg (population std; 0.0 if empty)."""
    arr = np.array([v for v in values if v is not None], dtype=np.float32)
    arr = arr[~np.isnan(arr)]
    if len(arr) == 0:
        return {s: 0.0 for s in SUFFIXES}
    return {
        "mean":  float(arr.mean()),
        "std":   float(arr.std()) if len(arr) > 1 else 0.0,
        "min":   float(arr.min()),
        "max":   float(arr.max()),
        "last":  float(arr[-1]),
        "range": float(arr.max() - arr.min()),
    }


def sample(mu: float, sd: float, missing_prob: float = 0.0):
    if random.random() < missing_prob:
        return None
    return random.gauss(mu, sd)


def deterioration(is_sep: bool, onset, h: int) -> float:
    """Sigmoid ramp toward sepsis onset (matches seed_data.py)."""
    if not is_sep or onset is None:
        return 0.0
    hours_to = onset - h
    if hours_to <= 0:
        return 1.0
    if hours_to <= 12:
        return 1.0 / (1.0 + np.exp(-(12 - hours_to) * 0.5 + 2))
    return 0.0


def build_patient(is_sep: bool) -> dict:
    age      = random.randint(30, 90)
    gender   = random.randint(0, 1)
    los      = random.randint(8, 48)
    hosp_adm = round(random.uniform(-72, 0), 1)
    onset    = random.randint(los // 3, max(los // 3 + 1, los - 4)) if is_sep else None

    vit_series = {c: [] for c in VITALS_NORMAL}
    lab_series = {c: [] for c in LABS_NORMAL}

    # Vitals every hour
    for h in range(1, los + 1):
        det = deterioration(is_sep, onset, h)
        for c, (mu, sd) in VITALS_NORMAL.items():
            vit_series[c].append(sample(mu + det * SEP_DELTAS.get(c, 0), sd * 1.2, 0.02))

    # Labs every 4 hours
    for h in range(4, los + 1, 4):
        det = deterioration(is_sep, onset, h)
        for c, (mu, sd) in LABS_NORMAL.items():
            mp = 0.4 if c in ("troponin_i", "ast", "bun") else 0.15
            lab_series[c].append(sample(mu + det * SEP_DELTAS.get(c, 0), sd * 1.2, mp))

    row = {}
    for c, name in VITAL_NAME.items():
        for suf, val in agg(vit_series[c]).items():
            row[f"{name}_{suf}"] = val
    for c, name in LAB_NAME.items():
        for suf, val in agg(lab_series[c]).items():
            row[f"{name}_{suf}"] = val
    row["Age"]         = float(age)
    row["Gender"]      = float(gender)
    row["HospAdmTime"] = float(hosp_adm)
    row["SepsisLabel"] = int(is_sep)
    return row


def main(n_patients: int, sepsis_rate: float, seed: int):
    random.seed(seed)
    np.random.seed(seed)
    n_sep   = max(2, int(n_patients * sepsis_rate))
    sep_ids = set(random.sample(range(n_patients), n_sep))

    rows = [build_patient(i in sep_ids) for i in range(n_patients)]
    df = pd.DataFrame(rows)
    df.to_parquet(OUT, index=False)

    print(f"Wrote {len(df)} patients x {df.shape[1] - 1} features -> {OUT}")
    print(f"  Sepsis positives: {int(df['SepsisLabel'].sum())} ({df['SepsisLabel'].mean() * 100:.1f}%)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-patients", type=int, default=2000)
    ap.add_argument("--sepsis-rate", type=float, default=0.12)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    main(args.n_patients, args.sepsis_rate, args.seed)
