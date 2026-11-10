"""
SepNova — Seed Script
=======================
Generates synthetic ICU patient data and seeds it into Supabase.
Run this once to populate your database with demo patients.

Usage:
    cd SepNova
    pip install python-dotenv supabase numpy pandas pyarrow
    python scripts/seed_data.py [--n-patients 200]
"""
import argparse
import os
import sys
import random
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "backend" / ".env")

from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

WARDS = ["ICU-A", "ICU-B", "ICU-C", "MICU", "SICU"]
STATUSES = ["active"] * 8 + ["discharged"] * 2

# ── Feature distributions (PhysioNet-2019 compatible) ────────────────────────
VITALS_NORMAL = {
    "hr":    (85, 15), "o2sat": (97, 2),  "temp": (37.0, 0.6),
    "sbp":   (120, 18), "map":   (80, 12), "dbp":  (75, 10),
    "resp":  (17, 4),
}
LABS_NORMAL = {
    "lactate":          (1.5, 0.7),  "wbc":             (9.0, 3.5),
    "creatinine":       (1.0, 0.4),  "bilirubin_total":  (1.0, 0.7),
    "bilirubin_direct": (0.3, 0.2),  "platelets":        (220, 80),
    "glucose":          (120, 35),   "hgb":              (12.5, 2.0),
    "hct":              (38, 6),     "potassium":        (4.0, 0.5),
    "ph":               (7.40, 0.05), "paco2":            (40, 6),
    "hco3":             (24, 3.5),   "base_excess":      (0.0, 2.5),
    "ptt":              (30, 8),     "troponin_i":       (0.05, 0.08),
    "ast":              (30, 20),    "bun":              (18, 8),
    "calcium":          (9.0, 0.6),
}

SEP_DELTAS = {
    "hr": +25, "o2sat": -5, "temp": +1.2, "sbp": -25, "map": -20,
    "dbp": -15, "resp": +10, "lactate": +2.2, "wbc": +8.0,
    "creatinine": +1.2, "bilirubin_total": +2.0, "platelets": -80,
}


def rand(mu, sd, clip_lo=None, clip_hi=None, missing_prob=0.0):
    if random.random() < missing_prob:
        return None
    v = random.gauss(mu, sd)
    if clip_lo is not None: v = max(v, clip_lo)
    if clip_hi is not None: v = min(v, clip_hi)
    return round(v, 2)


def seed(n_patients: int = 200):
    db = create_client(SUPABASE_URL, SUPABASE_KEY)
    print(f"Seeding {n_patients} patients into Supabase…")

    np.random.seed(42)
    n_sepsis  = max(1, int(n_patients * 0.08))
    sep_ids   = set(random.sample(range(n_patients), n_sepsis))

    patients_inserted, vitals_inserted, labs_inserted = 0, 0, 0

    for i in range(n_patients):
        pid    = f"P-{i+1:05d}"
        is_sep = i in sep_ids
        age    = random.randint(30, 90)
        gender = random.randint(0, 1)
        los    = random.randint(8, 48)
        ward   = random.choice(WARDS)
        status = "active" if los < 40 else random.choice(["active", "discharged"])

        # Sepsis onset (middle third of stay)
        onset = random.randint(los // 3, max(los // 3 + 1, los - 4)) if is_sep else None

        # Insert patient
        try:
            db.table("patients").insert({
                "patient_id":     pid,
                "age":            age,
                "gender":         gender,
                "hosp_adm_time":  round(random.uniform(-72, 0), 1),
                "icu_los":        los,
                "ward":           ward,
                "status":         status,
            }).execute()
            patients_inserted += 1
        except Exception as e:
            if "duplicate" in str(e).lower():
                continue  # already seeded
            raise

        # Vitals per hour
        for h in range(1, los + 1):
            det = 0.0
            if is_sep and onset is not None:
                hours_to = onset - h
                if hours_to <= 0:
                    det = 1.0
                elif hours_to <= 12:
                    det = 1.0 / (1.0 + np.exp(-(12 - hours_to) * 0.5 + 2))

            row = {"patient_id": pid, "hour": h}
            for col, (mu, sd) in VITALS_NORMAL.items():
                delta = SEP_DELTAS.get(col, 0)
                row[col] = rand(mu + det * delta, sd * 1.2, missing_prob=0.02)
            try:
                db.table("vitals").insert(row).execute()
                vitals_inserted += 1
            except Exception:
                pass

        # Labs every 4 hours
        for h in range(4, los + 1, 4):
            det = 0.0
            if is_sep and onset is not None:
                hours_to = onset - h
                if hours_to <= 0: det = 1.0
                elif hours_to <= 12: det = 1.0 / (1.0 + np.exp(-(12 - hours_to) * 0.5 + 2))

            row = {"patient_id": pid, "hour": h}
            for col, (mu, sd) in LABS_NORMAL.items():
                delta = SEP_DELTAS.get(col, 0)
                mp = 0.4 if col in ("troponin_i", "ast", "bun") else 0.15
                row[col] = rand(mu + det * delta, sd * 1.2, missing_prob=mp)
            try:
                db.table("lab_results").insert(row).execute()
                labs_inserted += 1
            except Exception:
                pass

        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{n_patients} patients done…")

    print(f"\n✓ Inserted: {patients_inserted} patients, {vitals_inserted} vital rows, {labs_inserted} lab rows")
    print(f"  Sepsis patients: {n_sepsis}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-patients", type=int, default=200)
    args = parser.parse_args()
    seed(args.n_patients)
