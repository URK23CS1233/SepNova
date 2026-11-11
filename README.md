# SepNova — Early Sepsis Prediction & ICU Monitoring

Clinical **decision-support** dashboard for early sepsis risk in ICU patients.
**Stack:** Next.js 14 · FastAPI · Supabase · XGBoost + LightGBM stacking · Vercel

> **Decision support, not diagnosis.** SepNova does not diagnose sepsis, does not
> replace clinician judgement, and must not be used as the sole basis for any
> treatment decision. Always confirm with the attending clinician.

---

## Quick Start (Local)

### 1. Clone & enter the project

```bash
cd SepNova
```

### 2. Supabase setup

1. Go to [supabase.com](https://supabase.com) → New project
2. Open **SQL Editor** → paste & run the full contents of `database/schema.sql`
3. Copy your **Project URL**, **service_role key** and **JWT secret**
   (Settings → API)

### 3. Backend

```bash
cd backend
cp .env.example .env
# Fill in SUPABASE_URL, SUPABASE_SERVICE_KEY and SUPABASE_JWT_SECRET
# .env is gitignored — never commit it.

pip install -r requirements.txt

# Train the calibrated v3 model
python ml/train_v3.py --data ../outputs/step3_temporal.parquet

# Start the API
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs · health check: http://localhost:8000/health

Every `/api/v1/*` route requires a valid Supabase JWT with the right role.
Only `/health` and `/docs` are public.

### 4. Seed demo data (synthetic)

```bash
cd ..
python scripts/seed_data.py --n-patients 200
```

### 5. Frontend

```bash
cd frontend
cp .env.local.example .env.local
# Fill in NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY
# NEXT_PUBLIC_API_URL=http://localhost:8000

npm install
npm run dev
```

Open http://localhost:3000.

---

## Risk Levels & Alert Thresholds (single source of truth)

Risk bands are **not hardcoded in the routers**. They are derived at runtime from
the tuned operating threshold stored in the served artifact
(`backend/ml/artifacts/sepnova_model_v3.pkl`).

The current artifact has `threshold = 0.2078` (tuned for sensitivity ≥ 0.65).
The `[threshold, 1]` band is split into thirds for the three upper bands:

| Level    | Score range (current artifact) | Meaning |
|----------|--------------------------------|---------|
| Low      | `< 0.208`                      | Below the tuned alert threshold |
| Medium   | `0.208 – < 0.472`              | Above threshold, lower third |
| High     | `0.472 – < 0.736`              | Middle third — alert generated |
| Critical | `≥ 0.736`                      | Upper third — critical alert |

If the model is retrained, **all four cutoffs move automatically** with the new
threshold; update this table from `/api/v1/ml/metrics` (which returns
`threshold` and `alert_thresholds`). Do not edit router constants.

---

## Project Structure

```
SepNova/
├── frontend/               # Next.js 14 (App Router, TypeScript, Tailwind, SCSS)
│   └── src/
│       ├── app/
│       │   ├── dashboard/        # Bedside ward monitor
│       │   ├── simulate/         # Synthetic sepsis simulation
│       │   ├── patient/[id]/     # Patient detail
│       │   ├── alerts/           # Alert management
│       │   ├── results/          # Model performance metrics
│       │   └── insights/         # Novel insight endpoints
│       ├── components/           # BedTile, Waveform, RiskGauge, StatusStrip…
│       └── lib/                  # API client (attaches JWT) + Supabase client
├── backend/
│   ├── app/
│   │   ├── main.py               # App entry point + CORS
│   │   ├── auth.py               # JWT verification + role guards
│   │   ├── routers/              # patients, predictions, alerts, model, ml,
│   │   │                         # chat, admin, insights, simulate
│   │   └── models/ml_model.py    # Artifact loader, SHAP, missing-data flags
│   └── ml/
│       ├── features.py           # Shared train/inference feature pipeline
│       ├── train_v3.py           # Calibrated stacking trainer + reliability bins
│       ├── simulation.py         # Synthetic trajectory engine
│       ├── sofa.py               # SOFA / qSOFA
│       └── artifacts/            # Model (gitignored — never commit)
├── database/schema.sql
├── scripts/seed_data.py
└── outputs/                      # Generated data/parquet (gitignored)
```

---

## Model & Explainability

- **Served artifact:** `backend/ml/artifacts/sepnova_model_v3.pkl`
  (XGB + LGB + HGB + RF → LightGBM meta-learner → isotonic calibration).
- **Training target:** sepsis onset within the next 6 hours, using the past
  6 hours of vitals/labs.
- **SHAP:** every prediction returns the top-5 SHAP contributions from the XGB
  base estimator (`/api/v1/predictions`, `/api/v1/simulate`).
- **Missing data:** missing key inputs (lactate, MAP, HR, RR, temp, WBC,
  creatinine) are reported in `missing_features`, `data_complete` is set false,
  and `confidence` is reduced. Scores are never silently imputed without a flag.
- **Calibration:** `GET /api/v1/ml/calibration` returns the stored Brier score and
  a reliability table.

| Model        | AUROC  | AUPRC  | Sensitivity | Specificity |
|--------------|--------|--------|-------------|-------------|
| Ensemble v3  | 0.8434 | 0.5399 | 0.6582      | 0.8974      |

Metrics come from doubly out-of-fold, group-aware cross-validation on the
synthetic temporal dataset.

---

## Simulation (`/simulate`)

`POST /api/v1/simulate` generates a **synthetic** ICU trajectory (hourly HR, MAP,
RR, temp, SpO₂, WBC, lactate, creatinine, platelets, bilirubin, GCS) with a
configurable onset hour, severity and noise. For each hour it computes SOFA,
qSOFA and SIRS from the current window, scores the rolling 6-hour feature window
with the trained artifact, and returns the top SHAP drivers. The frontend replays
it with play/pause/step and a speed control, plotting model risk against the true
onset line and reporting **lead time in hours**.

The simulation never reads or writes patient data and is marked **SIMULATED**
on every screen.

---

## Real vs Synthetic Data

| Source | What it is |
|--------|------------|
| `scripts/generate_training_data.py` / `outputs/step3_temporal.parquet` | **Synthetic** PhysioNet-like ICU data used to train and evaluate the model. |
| `scripts/seed_data.py` | **Synthetic** demo patients seeded into Supabase. |
| `/simulate` | **Synthetic** hourly trajectory generated on request. |
| `vitals`, `lab_results`, `patients` in a connected Supabase project | **Potentially real** if you point SepNova at a real database. No PHI is included in this repository. |

Nothing in this repository is real patient data. Connecting a real ICU feed
requires an appropriate governance, security and regulatory review.

---

## Known Limitations

- The model is trained and validated on **synthetic data**; there is no external
  clinical validation and performance on real ICU populations is unknown.
- SOFA is computed with simplifications: no vasopressor doses, no PaO₂/FiO₂ when
  only SpO₂ is available, and GCS is treated as a monitored but non-model input.
- SHAP values explain the XGB base estimator, not the full calibrated stack.
- The reliability table shipped with the current artifact was computed
  in-sample on the training distribution and is optimistic; retraining produces
  doubly out-of-fold bins.
- Missing values use the training sentinel (`0.0`) for scoring; they are reported
  but natively-missing-aware modelling is future work.
- Not a medical device. Not FDA-cleared or CE-marked. No diagnosis, no
  prescribing, no autonomous treatment decisions.

---

## Security Notes

- `backend/.env`, `frontend/.env.local`, `.next/`, and all `*.pkl` model
  artifacts are ignored by git and are no longer tracked.
- Only `.env.example` / `.env.local.example` (placeholders) are committed.
- All API routes except `/health` (and `/docs`) require a JWT and a role check.
- Prediction responses are filtered through `ROLE_ALLOWED_PREDICTION_FIELDS`.

---

## Deploy

1. Push to GitHub (secrets are ignored).
2. Connect the repo to [vercel.com](https://vercel.com) for the frontend.
3. Set `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
   `NEXT_PUBLIC_API_URL` in the Vercel dashboard.
4. Deploy the backend to Fly.io / Railway with the same env vars, plus
   `SUPABASE_JWT_SECRET` and a `MODEL_PATH` pointing at the v3 artifact.

---

## Research Paper

This project is the basis of a paper submitted to **ICCDA3 2026**
(3rd International Conference on Computing and Data Analytics)
Track: *Data Science, Analytics and Applications*
Conference: 4–5 November 2026, Salalah, Oman
Publication: IEEE Xplore (Scopus-indexed)
