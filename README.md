# SepNova — Early Sepsis Prediction & ICU Monitoring

AI-powered clinical dashboard for early sepsis detection in ICU patients.  
**Stack:** Next.js 14 · FastAPI · Supabase · XGBoost + LightGBM Ensemble · Vercel

---

## Quick Start (Local)

### 1. Clone & enter the project

```bash
cd SepNova
```

### 2. Supabase setup

1. Go to [supabase.com](https://supabase.com) → New project
2. Open **SQL Editor** → paste & run the full contents of `database/schema.sql`
3. Copy your **Project URL** and **service_role key** (Settings → API)

### 3. Backend

```bash
cd backend
cp .env.example .env
# Fill in SUPABASE_URL and SUPABASE_SERVICE_KEY in .env

pip install -r requirements.txt

# Train the model (uses the synthetic data generated previously)
python ml/train.py --data ../outputs/step2.parquet --push-to-supabase

# Start the API
uvicorn app.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

### 4. Seed demo data

```bash
cd ..
python scripts/seed_data.py --n-patients 200
```

Then run batch predictions:

```bash
cd backend
python ml/predict.py
```

### 5. Frontend

```bash
cd frontend
cp .env.local.example .env.local
# Fill in NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY
# NEXT_PUBLIC_API_URL=http://localhost:8000

npm install
npm run dev
```

Open http://localhost:3000 — the dashboard is live.

---

## Project Structure

```
SepNova/
├── frontend/               # Next.js 14 (App Router, TypeScript, Tailwind)
│   └── src/
│       ├── app/
│       │   ├── page.tsx          # Ward Overview (main dashboard)
│       │   ├── patient/[id]/     # Patient detail + vitals charts
│       │   ├── alerts/           # Alert management
│       │   └── results/          # Model performance metrics
│       ├── components/           # Shared UI components
│       └── lib/                  # API client + Supabase client
├── backend/                # FastAPI (Python)
│   ├── app/
│   │   ├── main.py               # App entry point + CORS
│   │   ├── routers/              # patients, predictions, alerts, model
│   │   ├── models/               # Pydantic schemas + ML model loader
│   │   └── ml_utils.py           # Feature builder from Supabase
│   └── ml/
│       ├── train.py              # Training pipeline
│       ├── predict.py            # Batch prediction script
│       └── artifacts/            # Saved model (gitignored)
├── database/
│   └── schema.sql                # Full Supabase schema (run this first)
├── scripts/
│   └── seed_data.py              # Seed 200 synthetic ICU patients
└── vercel.json                   # Vercel deployment config
```

---

## Deploy to Vercel

1. Push to GitHub
2. Connect repo to [vercel.com](https://vercel.com)
3. Set environment variables in Vercel dashboard:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `NEXT_PUBLIC_API_URL` → your deployed backend URL
4. `vercel --prod`

For the backend, deploy to [Fly.io](https://fly.io) or [Railway](https://railway.app):

```bash
# Example: Railway
railway init
railway up
```

---

## ML Model

| Model          | AUROC | AUPRC | Sensitivity | Specificity |
|----------------|-------|-------|-------------|-------------|
| Logistic Reg   | ~0.78 | —     | —           | —           |
| Random Forest  | ~0.87 | —     | —           | —           |
| XGBoost        | ~0.86 | —     | —           | —           |
| LightGBM       | ~0.85 | —     | —           | —           |
| **Ensemble**   | **~0.87** | — | **~42%** | **~91%** |

Risk thresholds:
- 🟢 **Low**      < 25%
- 🟡 **Medium**   25–45%
- 🟠 **High**     45–70%
- 🔴 **Critical** ≥ 70%

---

## Research Paper

This project is the basis of a paper submitted to **ICCDA3 2026**  
(3rd International Conference on Computing and Data Analytics)  
Track: *Data Science, Analytics and Applications*  
Conference: 4–5 November 2026, Salalah, Oman  
Publication: IEEE Xplore (Scopus-indexed)
