"""
SepNova Model Loader
=====================
Unified interface over three artifact generations:
  • v1  — XGB + LGB weighted average        (keys: xgb, lgb)
  • v2  — stacking ensemble                  (keys: base_models, meta_model)
  • v3  — stacking + isotonic calibration    (keys: base_models, meta_model, calibrator)

Callers always use the same API:  model.predict(features_dict) -> {risk_score, risk_level, model_version}
The risk level is derived from the artifact's TUNED threshold (not hardcoded cutoffs).
"""
import joblib
import numpy as np
from pathlib import Path
from functools import lru_cache
from ..config import get_settings


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

    @property
    def is_stacked(self) -> bool:
        return bool(self._base_models) and (self._meta_model is not None or self._calibrator is not None)

    @property
    def trained_at(self):
        return self._artifact.get("trained_at")

    def _featurise(self, features: dict):
        """1-row DataFrame with the exact training column names (avoids LGB warnings)."""
        import pandas as pd
        return pd.DataFrame([{f: float(features.get(f, 0.0)) for f in self.feature_names}])

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

        return {
            "risk_score":    round(score, 4),
            "risk_level":    score_to_level(score, self.threshold),
            "xgb_score":     round(xgb_score, 4),
            "lgb_score":     round(lgb_score, 4),
            "model_version": self.version,
        }

    def predict_batch(self, features_list: list[dict]) -> list[dict]:
        return [self.predict(f) for f in features_list]

    def get_metrics(self) -> dict:
        return self._artifact.get("metrics", {})


@lru_cache()
def get_model() -> SepNovaModel:
    path = Path(get_settings().model_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Model artifact not found at {path}.\n"
            "  Train it first:  cd backend && python ml/train_v3.py"
        )
    return SepNovaModel(str(path))
