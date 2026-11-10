"""
Backward-compatible shim.

Historically build_patient_features() aggregated a patient's ENTIRE vitals/labs
history into raw base stats only — which silently zeroed every engineered feature
the v3 model expects (flags/trends/interactions/SOFA) AND used the wrong time span.
It now delegates to the single shared inference pipeline so the batch endpoint and
ml/predict.py produce exactly the windowed, fully-engineered 223-feature vector the
model was trained on. Prefer importing app.inference_features.build_patient_feature_vector
directly in new code.
"""
from supabase import Client
from .inference_features import build_patient_feature_vector


def build_patient_features(patient_id: str, db: Client) -> dict[str, float]:
    return build_patient_feature_vector(patient_id, db)
