"""
SepNova v3 — End-to-end verification (no DB / no server required)
=================================================================
Proves the three things that matter for a correct production ML pipeline:

  1. FEATURE CONTRACT PARITY — every feature the trained model expects is produced
     by the SHARED features.py pipeline (the exact code insights.py runs at
     inference). No model feature is silently defaulted to 0.
  2. THE INFERENCE PATH WORKS — readings -> compute_base_stats -> build_feature_vector
     -> SepNovaModel.predict returns a calibrated score + risk level.
  3. THE MODEL IS DISCRIMINATIVE & DETERMINISTIC — a septic-looking 6h window scores
     higher than a normal one, and identical input yields identical output.

Usage:  cd backend && python ml/verify_v3.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))          # backend/ml
sys.path.insert(0, str(Path(__file__).parent.parent))   # backend
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from features import compute_base_stats, build_feature_vector, PARAMETERS
from app.models.ml_model import SepNovaModel

ARTIFACT = Path(__file__).parent / "artifacts" / "sepnova_model.pkl"


def _readings(profile: dict, hours=6) -> list:
    """Build a 6h long-format reading list from a {param: value} profile."""
    out = []
    for h in range(hours):
        for p, v in profile.items():
            out.append({"parameter": p, "value": v})
    return out


NORMAL = {"HR": 78, "O2SAT": 98, "TEMP": 36.9, "SBP": 122, "MAP": 85, "DBP": 74,
          "RESP": 15, "Lactate": 1.2, "WBC": 7.5, "Creatinine": 0.9, "Platelets": 240,
          "pH": 7.41, "BUN": 14}
SEPTIC = {"HR": 122, "O2SAT": 90, "TEMP": 38.9, "SBP": 92, "MAP": 58, "DBP": 48,
          "RESP": 28, "Lactate": 4.6, "WBC": 19.0, "Creatinine": 2.3, "Platelets": 85,
          "pH": 7.29, "BUN": 34}


def main() -> int:
    if not ARTIFACT.exists():
        print(f"FAIL: artifact missing at {ARTIFACT} (run train_v3.py first)")
        return 1
    model = SepNovaModel(str(ARTIFACT))
    print(f"Loaded model {model.version} | {len(model.feature_names)} features | "
          f"threshold {model.threshold} | stacked={model.is_stacked}")

    ok = True

    # 1. Feature-contract parity ------------------------------------------------
    stats = compute_base_stats(_readings(SEPTIC))
    stats.update({"Age": 70.0, "Gender": 1.0, "HospAdmTime": -8.0})
    built = build_feature_vector(stats)
    built_keys, model_keys = set(built), set(model.feature_names)
    missing = model_keys - built_keys            # model wants but pipeline never makes
    extra   = built_keys - model_keys            # pipeline makes but model ignores
    print("\n[1] Feature-contract parity")
    print(f"    model features : {len(model_keys)}")
    print(f"    built features : {len(built_keys)}")
    print(f"    MISSING (silently-zero at inference): {len(missing)} -> {sorted(missing)[:8]}")
    print(f"    extra (ignored by model)           : {len(extra)} -> {sorted(extra)[:8]}")
    if missing:
        ok = False
        print("    >>> PARITY FAIL: model expects features the live pipeline never produces.")
    else:
        print("    >>> PASS: every model feature is produced by the shared pipeline.")

    # 2. Inference path works + 3. discriminative + deterministic ---------------
    def score(profile):
        s = compute_base_stats(_readings(profile))
        s.update({"Age": 70.0, "Gender": 1.0, "HospAdmTime": -8.0})
        return model.predict(build_feature_vector(s))

    r_norm, r_sep = score(NORMAL), score(SEPTIC)
    r_sep2 = score(SEPTIC)
    print("\n[2/3] Inference path + discrimination + determinism")
    print(f"    normal  -> risk {r_norm['risk_score']:.4f} ({r_norm['risk_level']})")
    print(f"    septic  -> risk {r_sep['risk_score']:.4f} ({r_sep['risk_level']})")
    if r_sep["risk_score"] <= r_norm["risk_score"]:
        ok = False
        print("    >>> FAIL: septic window did not score higher than normal.")
    else:
        print("    >>> PASS: septic window scores higher than normal.")
    if abs(r_sep["risk_score"] - r_sep2["risk_score"]) > 1e-9:
        ok = False
        print("    >>> FAIL: non-deterministic prediction.")
    else:
        print("    >>> PASS: deterministic.")

    print("\nRESULT:", "ALL CHECKS PASSED" if ok else "CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
