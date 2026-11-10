"""
SepNova — Training Pipeline
============================
Trains XGBoost + LightGBM ensemble on the synthetic (or real PhysioNet) dataset,
saves the model artifact, and writes the run record to Supabase.

Usage:
    cd backend
    python ml/train.py [--data path/to/step2.parquet] [--push-to-supabase]
"""
import argparse
import sys
import os
import warnings
import json
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    roc_auc_score, average_precision_score,
    f1_score, confusion_matrix,
)
from imblearn.over_sampling import SMOTE
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier

warnings.filterwarnings("ignore")

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).parent
ARTIFACT   = ROOT / "artifacts" / "sepnova_model.pkl"
ARTIFACT.parent.mkdir(parents=True, exist_ok=True)


def load_data(path: str) -> tuple[np.ndarray, np.ndarray, list[str]]:
    df = pd.read_parquet(path)
    label_col = "SepsisLabel" if "SepsisLabel" in df.columns else "y"
    y = df[label_col].values
    drop = {label_col, "pid", "patient_id", "ICULOS"}
    X_df = df.drop(columns=[c for c in drop if c in df.columns])
    feat_names = list(X_df.columns)
    X = X_df.fillna(0).values.astype(np.float32)
    return X, y, feat_names


def train(data_path: str, push_supabase: bool = False):
    print(f"Loading data: {data_path}")
    X, y, feat_names = load_data(data_path)
    print(f"  Shape: {X.shape} | Sepsis: {y.sum()} ({y.mean()*100:.1f}%)")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print("Applying SMOTE…")
    sm = SMOTE(sampling_strategy=0.35, random_state=42)
    X_res, y_res = sm.fit_resample(X_train, y_train)
    print(f"  After SMOTE: {X_res.shape}, sepsis={y_res.sum()}")

    # ── XGBoost ──────────────────────────────────────────────────────────────
    print("Training XGBoost…")
    scale_pos = (y_res == 0).sum() / max((y_res == 1).sum(), 1)
    xgb = XGBClassifier(
        n_estimators=200, max_depth=5, learning_rate=0.08,
        subsample=0.8, colsample_bytree=0.8,
        scale_pos_weight=scale_pos,
        use_label_encoder=False, eval_metric="logloss",
        random_state=42, n_jobs=-1, verbosity=0,
    )
    xgb.fit(X_res, y_res)

    # ── LightGBM ─────────────────────────────────────────────────────────────
    print("Training LightGBM…")
    lgb = LGBMClassifier(
        n_estimators=200, num_leaves=31, learning_rate=0.08,
        subsample=0.8, colsample_bytree=0.8,
        class_weight="balanced",
        random_state=42, n_jobs=-1, verbose=-1,
    )
    lgb.fit(X_res, y_res)

    # ── Ensemble (weighted average) ───────────────────────────────────────────
    xgb_prob = xgb.predict_proba(X_test)[:, 1]
    lgb_prob = lgb.predict_proba(X_test)[:, 1]
    ens_prob  = 0.55 * xgb_prob + 0.45 * lgb_prob

    # ── Metrics ───────────────────────────────────────────────────────────────
    THRESHOLD = 0.40
    ens_pred = (ens_prob >= THRESHOLD).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, ens_pred).ravel()

    metrics = {
        "auroc":       round(roc_auc_score(y_test, ens_prob), 4),
        "auprc":       round(average_precision_score(y_test, ens_prob), 4),
        "sensitivity": round(tp / max(tp + fn, 1), 4),
        "specificity": round(tn / max(tn + fp, 1), 4),
        "f1_score":    round(f1_score(y_test, ens_pred), 4),
        "threshold":   THRESHOLD,
        "n_patients":  len(X),
        "n_sepsis":    int(y.sum()),
    }

    print("\n─── Ensemble Results ───────────────────────────────")
    for k, v in metrics.items():
        print(f"  {k:15s} {v}")

    # ── Save artifact ─────────────────────────────────────────────────────────
    artifact = {
        "xgb":          xgb,
        "lgb":          lgb,
        "feature_names": feat_names,
        "version":       "v1.0",
        "trained_at":    datetime.now(timezone.utc).isoformat(),
        "metrics":       metrics,
    }
    joblib.dump(artifact, ARTIFACT)
    print(f"\nModel saved → {ARTIFACT}")

    # ── Push to Supabase ──────────────────────────────────────────────────────
    if push_supabase:
        try:
            from dotenv import load_dotenv
            load_dotenv(ROOT.parent / ".env")
            from supabase import create_client
            sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
            sb.table("model_runs").insert({
                "run_name":    f"SepNova-Ensemble-{datetime.now().strftime('%Y%m%d-%H%M')}",
                "model_type":  "XGBoost+LightGBM Ensemble",
                "parameters":  json.dumps({"xgb_weight": 0.55, "lgb_weight": 0.45, "smote": 0.35, "threshold": THRESHOLD}),
                **metrics,
            }).execute()
            print("Run record pushed to Supabase ✓")
        except Exception as e:
            print(f"⚠ Supabase push failed: {e}")

    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="../outputs/step2.parquet",
                        help="Path to aggregated patient-level parquet")
    parser.add_argument("--push-to-supabase", action="store_true")
    args = parser.parse_args()
    train(args.data, args.push_to_supabase)
