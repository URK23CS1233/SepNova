"""
SepNova v3 — Prospective Early-Warning Training Pipeline
========================================================
Trains on the TEMPORAL dataset (outputs/step3_temporal.parquet) where each row is
a patient-hour summarised over the past 6h and the label is future sepsis onset
within 6h. Fixes the leakage + wrong-target problems of v1/v2.

Pipeline
--------
  1. Feature engineering via the SHARED features.py (identical at inference time).
  2. StratifiedGroupKFold (group = patient_id) — NO patient appears in both train
     and validation, so there is no patient-level leakage across folds.
  3. SMOTE (sampling_strategy=0.35) applied INSIDE each training fold only.
  4. Base models: XGBoost (Optuna), LightGBM (Optuna), HistGradientBoosting,
     RandomForest. Out-of-fold (OOF) predictions feed a LightGBM meta-learner.
  5. Isotonic probability calibration (CalibratedClassifierCV, cv='prefit') wraps
     the meta-learner so the served probability is well-calibrated.
  6. Decision threshold tuned for sensitivity >= 0.65 (maximising specificity).

Artifact (backend/ml/artifacts/sepnova_model_v3.pkl) keys:
    version, base_models [(name, model)], meta_model, calibrator, feature_names,
    threshold, metrics, trained_at

Usage:
    cd backend
    python ml/train_v3.py [--data ../outputs/step3_temporal.parquet]
                          [--trials 30] [--push-to-supabase]
"""
import argparse
import json
import logging
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import joblib

try:                                              # Windows console is cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent))   # backend/ml on path
from features import build_feature_vector

import optuna
from optuna.samplers import TPESampler
from sklearn.base import clone
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    roc_auc_score, average_precision_score, f1_score,
    confusion_matrix, precision_recall_curve, brier_score_loss,
)
from imblearn.over_sampling import SMOTE
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)
logging.basicConfig(format="%(message)s", level=logging.INFO)
log = logging.getLogger("train_v3")

ROOT     = Path(__file__).parent
ARTIFACT = ROOT / "artifacts" / "sepnova_model_v3.pkl"
ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
SEED     = 42
N_FOLDS  = 5
SMOTE_RATIO = 0.35
META_COLS   = ["xgb", "lgb", "hgb", "rf"]


# ─────────────────────────────────────────────────────────────────────────────
# 1. LOAD + ENGINEER  (shared features.py => train/inference parity)
# ─────────────────────────────────────────────────────────────────────────────

def load_data(path: str):
    df = pd.read_parquet(path)
    meta = {"patient_id", "hour", "SepsisLabel"}
    base_cols = [c for c in df.columns if c not in meta]

    records = df[base_cols].to_dict("records")
    X = pd.DataFrame([build_feature_vector(r) for r in records]).fillna(0.0).astype(np.float32)

    y      = df["SepsisLabel"].to_numpy(dtype=int)
    groups = df["patient_id"].to_numpy()
    feature_names = list(X.columns)
    log.info(f"  Loaded {len(X)} patient-hours · {X.shape[1]} engineered features · "
             f"{int(y.sum())} positive ({100*y.mean():.2f}%) · {len(set(groups))} patients")
    return X, y, groups, feature_names


# ─────────────────────────────────────────────────────────────────────────────
# 2. OPTUNA (group-aware inner CV — no patient leakage during tuning)
# ─────────────────────────────────────────────────────────────────────────────

def _inner_cv_auroc(make_model, params, Xv, y, groups):
    sgkf = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=SEED)
    scores = []
    for tr, va in sgkf.split(Xv, y, groups):
        Xr, yr = SMOTE(sampling_strategy=SMOTE_RATIO, random_state=SEED).fit_resample(Xv[tr], y[tr])
        m = make_model(params)
        m.fit(Xr, yr)
        scores.append(roc_auc_score(y[va], m.predict_proba(Xv[va])[:, 1]))
    return float(np.mean(scores))


def tune_xgb(X, y, groups, n_trials):
    Xv = X.to_numpy(dtype=np.float32)

    def make(p):
        return XGBClassifier(**p, use_label_encoder=False, eval_metric="aucpr",
                             tree_method="hist", random_state=SEED, n_jobs=-1, verbosity=0)

    def objective(trial):
        p = {
            "n_estimators":     trial.suggest_int("n_estimators", 200, 500),
            "max_depth":        trial.suggest_int("max_depth", 3, 8),
            "learning_rate":    trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "subsample":        trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
            "gamma":            trial.suggest_float("gamma", 0.0, 3.0),
            "reg_lambda":       trial.suggest_float("reg_lambda", 0.5, 5.0),
        }
        return _inner_cv_auroc(make, p, Xv, y, groups)

    study = optuna.create_study(direction="maximize", sampler=TPESampler(seed=SEED))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    log.info(f"  Best XGB AUROC {study.best_value:.4f}")
    return study.best_params


def tune_lgb(X, y, groups, n_trials):
    Xv = X.to_numpy(dtype=np.float32)

    def make(p):
        return LGBMClassifier(**p, class_weight="balanced",
                              random_state=SEED, n_jobs=-1, verbose=-1)

    def objective(trial):
        p = {
            "n_estimators":      trial.suggest_int("n_estimators", 200, 500),
            "num_leaves":        trial.suggest_int("num_leaves", 20, 100),
            "learning_rate":     trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "subsample":         trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 50),
            "reg_lambda":        trial.suggest_float("reg_lambda", 0.0, 5.0),
        }
        return _inner_cv_auroc(make, p, Xv, y, groups)

    study = optuna.create_study(direction="maximize", sampler=TPESampler(seed=SEED))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    log.info(f"  Best LGB AUROC {study.best_value:.4f}")
    return study.best_params


# ─────────────────────────────────────────────────────────────────────────────
# 3. BASE MODELS + STACKING
# ─────────────────────────────────────────────────────────────────────────────

def build_base_models(xgb_params, lgb_params):
    return [
        ("xgb", XGBClassifier(**xgb_params, use_label_encoder=False, eval_metric="aucpr",
                              tree_method="hist", random_state=SEED, n_jobs=-1, verbosity=0)),
        ("lgb", LGBMClassifier(**lgb_params, class_weight="balanced",
                               random_state=SEED, n_jobs=-1, verbose=-1)),
        ("hgb", HistGradientBoostingClassifier(max_iter=400, max_leaf_nodes=40,
                                               learning_rate=0.08, class_weight="balanced",
                                               random_state=SEED)),
        ("rf",  RandomForestClassifier(n_estimators=300, min_samples_leaf=2,
                                       class_weight="balanced_subsample",
                                       random_state=SEED, n_jobs=-1)),
    ]


def make_meta():
    """The LightGBM meta-learner configuration (used for both evaluation and serving)."""
    return LGBMClassifier(n_estimators=200, num_leaves=16, learning_rate=0.05,
                          subsample=0.8, colsample_bytree=0.8, class_weight="balanced",
                          random_state=SEED, n_jobs=-1, verbose=-1)


def compute_oof_base(X, y, groups, base_models):
    """5-fold group OOF base predictions — leakage-free per sample (no patient spans folds)."""
    n = len(X)
    oof = np.zeros((n, len(base_models)), dtype=np.float32)
    sgkf = StratifiedGroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)

    for fold, (tr, va) in enumerate(sgkf.split(X, y, groups)):
        Xr, yr = SMOTE(sampling_strategy=SMOTE_RATIO, random_state=SEED + fold).fit_resample(
            X.iloc[tr], y[tr])
        for mi, (name, proto) in enumerate(base_models):
            m = clone(proto)
            m.fit(Xr, yr)
            oof[va, mi] = m.predict_proba(X.iloc[va])[:, 1]
        log.info(f"  Fold {fold+1}/{N_FOLDS} base done (avg-base OOF AUROC "
                 f"{roc_auc_score(y[va], oof[va].mean(axis=1)):.4f})")

    oof_df = pd.DataFrame(oof, columns=[nm for nm, _ in base_models])
    for mi, (name, _) in enumerate(base_models):
        log.info(f"    {name:4s} OOF AUROC {roc_auc_score(y, oof[:, mi]):.4f}")
    return oof_df


def nested_meta_oof(oof_df, y, groups):
    """
    HONEST, doubly out-of-fold calibrated stack predictions. A second group-aware CV
    over the base-OOF matrix: per fold a fresh meta-LGB + isotonic calibrator is fit on
    the training patients and predicts the held-out patients. Used ONLY for metrics +
    threshold, so the reported numbers are never computed on rows the meta/calibrator saw.
    """
    from sklearn.isotonic import IsotonicRegression
    cal_oof = np.zeros(len(oof_df), dtype=float)
    sgkf = StratifiedGroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED + 7)
    for tr, va in sgkf.split(oof_df, y, groups):
        m = make_meta()
        m.fit(oof_df.iloc[tr], y[tr])
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(m.predict_proba(oof_df.iloc[tr])[:, 1], y[tr])
        cal_oof[va] = iso.predict(m.predict_proba(oof_df.iloc[va])[:, 1])
    return cal_oof


def find_best_threshold(y_true, y_prob, min_sensitivity=0.65):
    prec, rec, thr = precision_recall_curve(y_true, y_prob)
    best_t, best_spec = 0.40, -1.0
    for t, sens in zip(thr, rec[:-1]):
        if sens >= min_sensitivity:
            pred = (y_prob >= t).astype(int)
            tn = int(((pred == 0) & (y_true == 0)).sum())
            fp = int(((pred == 1) & (y_true == 0)).sum())
            spec = tn / max(tn + fp, 1)
            if spec > best_spec:
                best_spec, best_t = spec, float(t)
    return best_t


# ─────────────────────────────────────────────────────────────────────────────
# 4. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def train(data_path, n_trials=30, push_supabase=False):
    log.info("=" * 60)
    log.info("SepNova v3 — Prospective Early-Warning Training")
    log.info("=" * 60)

    log.info("\n[1/6] Loading + engineering features ...")
    X, y, groups, feature_names = load_data(data_path)

    log.info(f"\n[2/6] Optuna XGBoost ({n_trials} trials, group-aware) ...")
    xgb_params = tune_xgb(X, y, groups, n_trials)
    log.info(f"\n[3/6] Optuna LightGBM ({n_trials} trials, group-aware) ...")
    lgb_params = tune_lgb(X, y, groups, n_trials)

    log.info(f"\n[4/6] {N_FOLDS}-fold group OOF base predictions ...")
    base_models = build_base_models(xgb_params, lgb_params)
    oof_df = compute_oof_base(X, y, groups, base_models)

    # HONEST metrics: evaluate the meta + calibration layer DOUBLY out-of-fold.
    log.info("\n[5/6] Doubly-OOF meta + isotonic evaluation + threshold tuning ...")
    cal_oof = nested_meta_oof(oof_df, y, groups)
    threshold = find_best_threshold(y, cal_oof, min_sensitivity=0.65)
    pred = (cal_oof >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
    metrics = {
        "auroc":       round(float(roc_auc_score(y, cal_oof)), 4),
        "auprc":       round(float(average_precision_score(y, cal_oof)), 4),
        "sensitivity": round(tp / max(tp + fn, 1), 4),
        "specificity": round(tn / max(tn + fp, 1), 4),
        "f1_score":    round(float(f1_score(y, pred)), 4),
        "brier":       round(float(brier_score_loss(y, cal_oof)), 4),
        "threshold":   round(threshold, 4),
        "n_patients":  int(len(set(groups))),
        "n_samples":   int(len(y)),
        "n_positive":  int(y.sum()),
        "prevalence":  round(float(y.mean()), 4),
        "n_features":  int(X.shape[1]),
        "horizon_hours": 6,
        "window_hours":  6,
    }

    # Served stack: meta + isotonic calibrator fit on the FULL base-OOF matrix, and base
    # models refit on all data. (The metrics above come from the doubly-OOF eval, NOT these.)
    log.info("\n[6/6] Fitting served meta+calibrator + base models, saving ...")
    meta = make_meta()
    meta.fit(oof_df, y)
    calibrator = CalibratedClassifierCV(meta, method="isotonic", cv="prefit")
    calibrator.fit(oof_df, y)

    Xr_full, yr_full = SMOTE(sampling_strategy=SMOTE_RATIO, random_state=SEED).fit_resample(X, y)
    final_base = []
    for name, proto in base_models:
        m = clone(proto)
        m.fit(Xr_full, yr_full)
        final_base.append((name, m))

    # Top feature importances from the XGB base model (for the results dashboard).
    xgb_final = dict(final_base)["xgb"]
    imp = sorted(zip(feature_names, xgb_final.feature_importances_),
                 key=lambda kv: kv[1], reverse=True)[:8]
    metrics["top_features"] = [[name, round(float(score), 5)] for name, score in imp]

    artifact = {
        "version":       "v3.0",
        "base_models":   final_base,
        "meta_model":    meta,
        "calibrator":    calibrator,
        "feature_names": feature_names,
        "threshold":     round(threshold, 4),
        "metrics":       metrics,
        "trained_at":    datetime.now(timezone.utc).isoformat(),
        "xgb_params":    xgb_params,
        "lgb_params":    lgb_params,
    }
    joblib.dump(artifact, ARTIFACT)

    log.info("\n  ---- v3 results (doubly-OOF, group-CV, leakage-free) ----")
    for k in ("auroc", "auprc", "sensitivity", "specificity", "f1_score", "brier", "threshold"):
        log.info(f"    {k:12s} {metrics[k]}")
    log.info(f"    features     {metrics['n_features']}")
    log.info(f"  Saved -> {ARTIFACT}")

    if push_supabase:
        try:
            from dotenv import load_dotenv
            load_dotenv(ROOT.parent / ".env")
            import os
            from supabase import create_client
            sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
            sb.table("model_runs").insert({
                "run_name":   f"SepNova-v3-Temporal-{datetime.now().strftime('%Y%m%d-%H%M')}",
                "model_type": "Temporal stacking (XGB+LGB+HGB+RF) meta-LGB + isotonic · GroupKFold",
                "auroc": metrics["auroc"], "auprc": metrics["auprc"],
                "sensitivity": metrics["sensitivity"], "specificity": metrics["specificity"],
                "f1_score": metrics["f1_score"], "threshold": metrics["threshold"],
                "n_patients": metrics["n_patients"], "n_sepsis": metrics["n_positive"],
                "parameters": json.dumps({"xgb": xgb_params, "lgb": lgb_params,
                                          "smote": SMOTE_RATIO, "folds": N_FOLDS,
                                          "horizon_h": 6, "window_h": 6}),
            }).execute()
            log.info("  Run record pushed to Supabase.")
        except Exception as e:
            log.warning(f"  Supabase push skipped: {e}")

    return metrics


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="../outputs/step3_temporal.parquet")
    ap.add_argument("--trials", type=int, default=30)
    ap.add_argument("--push-to-supabase", action="store_true")
    args = ap.parse_args()
    train(args.data, n_trials=args.trials, push_supabase=args.push_to_supabase)
