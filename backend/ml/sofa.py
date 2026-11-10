"""
SepNova — SOFA & qSOFA Clinical Scoring
=========================================
Computes Sequential Organ Failure Assessment (SOFA) and Quick SOFA (qSOFA)
scores from patient vitals and lab data.

SOFA covers 6 organ systems:
  1. Respiratory  — PaO2/FiO2 (or SpO2-based surrogate)
  2. Coagulation  — Platelets
  3. Liver        — Bilirubin
  4. Cardiovascular — MAP / vasopressors
  5. CNS          — GCS (not available; set to 0 if missing)
  6. Renal        — Creatinine

qSOFA (bedside, 0–3):
  1. Respiratory Rate ≥ 22 bpm (+1)
  2. SBP ≤ 100 mmHg (+1)
  3. Altered mentation (GCS < 15 — skipped if GCS not recorded)

Reference: Singer et al. JAMA 2016;315(8):801-810 (Sepsis-3)
"""
from __future__ import annotations
import numpy as np


# ── SOFA sub-scores ───────────────────────────────────────────────────────────

def sofa_respiratory(pao2: float | None, fio2: float | None,
                     spo2: float | None = None) -> int:
    """
    Respiratory SOFA. Uses PaO2/FiO2 if available, else SpO2/FiO2 surrogate.
    SpO2/FiO2 ≈ PaO2/FiO2 × 0.61 + 91 (Rice 2007 approximation inverted).
    """
    if pao2 is not None and fio2 and fio2 > 0:
        ratio = pao2 / fio2
    elif spo2 is not None and fio2 and fio2 > 0:
        # Kigali modification: SpO2/FiO2 surrogate
        ratio = (spo2 / fio2) * 0.61 + 91  # convert back to PF ratio approximation
    else:
        return 0  # missing — assume normal

    if ratio >= 400: return 0
    if ratio >= 300: return 1
    if ratio >= 200: return 2
    if ratio >= 100: return 3
    return 4


def sofa_coagulation(platelets: float | None) -> int:
    if platelets is None: return 0
    if platelets >= 150: return 0
    if platelets >= 100: return 1
    if platelets >= 50:  return 2
    if platelets >= 20:  return 3
    return 4


def sofa_liver(bilirubin: float | None) -> int:
    """Bilirubin in mg/dL."""
    if bilirubin is None: return 0
    if bilirubin < 1.2:  return 0
    if bilirubin < 2.0:  return 1
    if bilirubin < 6.0:  return 2
    if bilirubin < 12.0: return 3
    return 4


def sofa_cardiovascular(map_val: float | None) -> int:
    """
    Without vasopressor data, use MAP only.
    Full SOFA needs dopamine/dobutamine doses — simplified here.
    """
    if map_val is None: return 0
    if map_val >= 70: return 0
    return 1   # MAP < 70 = score 1 (vasopressor data unavailable)


def sofa_renal(creatinine: float | None) -> int:
    """Creatinine in mg/dL."""
    if creatinine is None: return 0
    if creatinine < 1.2:  return 0
    if creatinine < 2.0:  return 1
    if creatinine < 3.5:  return 2
    if creatinine < 5.0:  return 3
    return 4


# ── Composite SOFA ────────────────────────────────────────────────────────────

def compute_sofa(
    pao2: float | None = None,
    fio2: float | None = None,
    spo2: float | None = None,
    platelets: float | None = None,
    bilirubin: float | None = None,
    map_val: float | None = None,
    creatinine: float | None = None,
) -> dict:
    resp   = sofa_respiratory(pao2, fio2, spo2)
    coag   = sofa_coagulation(platelets)
    liver  = sofa_liver(bilirubin)
    cardio = sofa_cardiovascular(map_val)
    renal  = sofa_renal(creatinine)
    total  = resp + coag + liver + cardio + renal

    return {
        "sofa_total":          total,
        "sofa_respiratory":    resp,
        "sofa_coagulation":    coag,
        "sofa_liver":          liver,
        "sofa_cardiovascular": cardio,
        "sofa_renal":          renal,
        # Sepsis-3: SOFA ≥ 2 → organ dysfunction
        "organ_dysfunction":   total >= 2,
    }


# ── qSOFA ─────────────────────────────────────────────────────────────────────

def compute_qsofa(
    resp_rate: float | None = None,
    sbp: float | None = None,
    gcs: float | None = None,      # optional
) -> dict:
    score = 0
    components = {}

    if resp_rate is not None:
        rr_flag = resp_rate >= 22
        score += int(rr_flag)
        components["rr_flag"] = rr_flag

    if sbp is not None:
        sbp_flag = sbp <= 100
        score += int(sbp_flag)
        components["sbp_flag"] = sbp_flag

    if gcs is not None:
        gcs_flag = gcs < 15
        score += int(gcs_flag)
        components["gcs_flag"] = gcs_flag

    components["qsofa_total"] = score
    # High risk: qSOFA ≥ 2
    components["high_risk_qsofa"] = score >= 2
    return components


# ── Batch computation from time-series rows ───────────────────────────────────

def sofa_from_rows(vitals_rows: list[dict], lab_rows: list[dict]) -> list[dict]:
    """
    Compute SOFA + qSOFA for each available time-point.
    vitals_rows: list of dicts with keys: hour, hr, o2sat, sbp, map, resp, temp
    lab_rows:    list of dicts with keys: hour, paco2, fio2, platelets, bilirubin_total, creatinine, ph
    Returns list of {hour, sofa_total, qsofa_total, ...}
    """
    # Index labs by hour
    lab_by_hour: dict[int, dict] = {}
    for row in lab_rows:
        lab_by_hour[row["hour"]] = row

    results = []
    for v in vitals_rows:
        h = v["hour"]
        # Find nearest lab (within ±6h)
        lab = lab_by_hour.get(h)
        for delta in range(1, 7):
            if lab: break
            lab = lab_by_hour.get(h - delta) or lab_by_hour.get(h + delta)

        sofa = compute_sofa(
            pao2=None,
            fio2=lab.get("fio2") if lab else None,
            spo2=v.get("o2sat"),
            platelets=lab.get("platelets") if lab else None,
            bilirubin=lab.get("bilirubin_total") if lab else None,
            map_val=v.get("map"),
            creatinine=lab.get("creatinine") if lab else None,
        )
        qsofa = compute_qsofa(
            resp_rate=v.get("resp"),
            sbp=v.get("sbp"),
        )
        results.append({
            "hour": h,
            **sofa,
            **qsofa,
        })

    return results


def sofa_velocity(sofa_series: list[dict], window_h: int = 6) -> float:
    """
    Compute the rate of SOFA increase over the last `window_h` hours.
    Positive = deteriorating. Normalized to [0, 1] (cap at +4 points/6h).
    """
    if len(sofa_series) < 2:
        return 0.0
    recent = sorted(sofa_series, key=lambda x: x["hour"])
    if len(recent) < 2:
        return 0.0
    last  = recent[-1]["sofa_total"]
    early = next(
        (r["sofa_total"] for r in reversed(recent[:-1])
         if recent[-1]["hour"] - r["hour"] <= window_h),
        recent[0]["sofa_total"]
    )
    delta = last - early
    return float(np.clip(delta / 4.0, 0.0, 1.0))  # normalized [0,1]
