# SepNova – Run & Deploy Guide

This Markdown file walks you through **running the application locally**, **connecting it to a database**, and **deploying both the front‑end and back‑end on free hosting platforms** (Vercel/Netlify for the UI, Render/Railway for the API). Every command is shown on its own line – no “combined” commands.

---
## 1️⃣ Prerequisites (install once)

| Tool | Install command |
|------|-----------------|
| **Git** | `git install` (or `winget install Git.Git` on Windows) |
| **Node ≥ 18** | `node -v` – if missing, download from <https://nodejs.org/> or `brew install node` / `choco install nodejs` |
| **Python 3.12** (the repo was built for 3.12) | `python -v` – if missing, download from <https://python.org> or `brew install python@3.12` |
| **GitHub account** (free) – for pushing the code | <https://github.com/signup> |

---
## 2️⃣ Clone the repository

```bash
# 1️⃣ Create a folder wherever you want
mkdir SepNova
cd SepNova

# 2️⃣ Clone the repo (replace USER/REPO with the actual owner / name)
git clone https://github.com/USER/REPO.git .
```

*You now have the directory layout:*

```
SepNova/
├─ backend/
│  ├─ app/
│  ├─ ml/
│  ├─ .env.example
│  ├─ requirements.txt
│  └─ ...
└─ frontend/
   ├─ src/
   ├─ package.json
   ├─ .env.local.example
   └─ ...
```

---
## 3️⃣ Backend (FastAPI) – local run

| Step | Command (one line) | What it does |
|------|--------------------|--------------|
| **3.1** | `python -m venv .venv` | Create an isolated Python environment |
| **3.2** | `.venv\Scripts\activate` *(Windows)* or `source .venv/bin/activate` *(macOS/Linux)* | Activate the environment |
| **3.3** | `pip install --upgrade pip` | Upgrade pip to latest |
| **3.4** | `pip install -r backend/requirements.txt` | Install all Python dependencies (FastAPI, uvicorn, XGBoost, SHAP, etc.) |
| **3.5** | `cp backend/.env.example backend/.env` | Copy the placeholder env file |
| **3.6** | Edit `backend/.env` **yourself** – add your database connection string (see **4️⃣ Connect to a DB** below). Keep the line `MODEL_PATH=./ml/artifacts/sepnova_model_v3.pkl`. |
| **3.7** | `cd backend` |
| **3.8** | `.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8123` | Start the API server (default port **8123**) |

> **Result** – The backend is now listening at <http://127.0.0.1:8123>. Open <http://127.0.0.1:8123/docs> to see the Swagger UI.

### 3.9 (optional) Quick sanity check – one‑liner

```bash
# In a *new* shell, still inside the activated venv:
python -c "from app.main import app; print('31 routes loaded')"
```

---
## 4️⃣ Connect the backend to a database

The repo expects a **PostgreSQL** connection string (SQLAlchemy). A free hosted DB can be obtained via **Supabase**.

### 4.1 Create a Supabase project (one‑off)

1. Go to <https://supabase.com> and sign‑up/in.  
2. Click **New project** → give a name, choose a region.  
3. Wait until the project dashboard appears.

### 4.2 Obtain the connection string

In the Supabase dashboard:

| Item | Where to find it | Example |
|------|------------------|---------|
| **Project URL** | Settings → API → Project URL | `https://abcdefg.supabase.co` |
| **Database password** | SQL Editor → “Connect with password” → set a password | `postgres://postgres:password@db.xyz.supabase.com:5432/postgres` |

The **full DATABASE_URL** format that FastAPI/SQLAlchemy understands:

```
postgres://<user>:<password>@<host>:5432/postgres
```

### 4.3 Fill `backend/.env`

Edit the file you copied in step 3.6 and add (or replace) the line:

```text
DATABASE_URL=postgres://postgres:YOUR_SUPABASE_PASSWORD@db.xyz.supabase.com:5432/postgres
```

> **Important** – Keep the `.env` file **outside** Git tracking (it is already listed in `.gitignore`). Never commit real passwords.

### 4.4 Run database tables (manual or via SQL Editor)

```bash
# Inside the backend directory, still with venv activated
python - <<'PY'
from app.db.base import Base
import sqlalchemy as sa
engine = sa.create_engine("postgresql://postgres:YOUR_PASSWORD@db.xyz.supabase.com:5432/postgres")
Base.metadata.create_all(engine)   # creates any tables defined in models
PY
```

Or, using the Supabase SQL Editor, run the `backend/sql/init.sql` script if you have one.

### 4.5 Verify the connection

```bash
python -c "import sqlalchemy; eng = sqlalchemy.create_engine('postgres://postgres:YOUR_PASSWORD@db.xyz.supabase.com:5432/postgres'); print(eng.connect().execution_options(isolation_level='AUTOCOMMIT'))"
```

If no error appears, the backend can talk to the DB.

---
## 5️⃣ Frontend (Next.js + Tailwind) – local run

| Step | Command (one line) | What it does |
|------|--------------------|--------------|
| **5.1** | `cd frontend` | Enter the front‑end directory |
| **5.2** | `npm install` | Install Node dependencies (React, Next, Tailwind, shadcn‑ui, etc.) |
| **5.3** | `cp frontend/.env.local.example frontend/.env.local` | Copy placeholder env file |
| **5.4** | Edit `frontend/.env.local` and add your Supabase credentials (required by the API client):<br>`NEXT_PUBLIC_SUPABASE_URL=https://abcdefg.supabase.co`<br>`NEXT_PUBLIC_SUPABASE_ANON_KEY=YOUR_ANON_PUBLIC_KEY` | These values let the frontend authenticate users via Supabase (the same project you created in 4.1). |
| **5.5** | `npm run dev` | Start the development server (default **localhost:3000**) |

> **Result** – Open <http://localhost:3000> in a browser. The UI will call the backend at `http://127.0.0.1:8123` (the API client in `frontend/src/lib/api.ts` is pre‑configured for that host).

### 5.6 Quick test (no extra terminal)

From any shell with the venv active:

```bash
# Inside frontend, run a single curl against the backend:
curl -s http://127.0.0.1:8123/health
# Expected: {"detail":"OK"} or similar 200 response
```

---
## 6️⃣ Deploy the **backend** on a free platform

Below are two popular choices – pick one.

### 6.1 Render (free tier) – steps

1. **Push code to GitHub** (if not already there):

   ```bash
   git remote add origin git@github.com:USER/SEPNOVA.git   # replace with your repo
   git push -u origin main
   ```

2. **Create a new Web Service on Render**  
   * Go to <https://render.com> → New → Web Service.  
   * Connect your GitHub repo (`USER/SEPNOVA`).  
   * **Build Command**: `pip install -r backend/requirements.txt`  
   * **Start Command**: `gunicorn app.main:app -b 0.0.0.0:$PORT` (Render injects `$PORT`).  

3. **Set environment variables** (in the UI → “Environment” tab):  

   | Key | Value |
   |-----|-------|
   | `DATABASE_URL` | `postgres://postgres:YOUR_SUPABASE_PASSWORD@db.xyz.supabase.com:5432/postgres` |
   | `MODEL_PATH` | `./ml/artifacts/sepnova_model_v3.pkl` |
   | `SECRET_KEY` | any random string (used by FastAPI for JWT) |

4. **Deploy** – Render will build and start the service.  
   *Endpoint* will be something like `https://sepnova-backend.onrender.com`.

5. **Test** – Open the generated Swagger UI at `https://sepnova-backend.onrender.com/docs`.

### 6.2 Railway (free tier) – alternative

1. Same Git push as above.  
2. New project → “Deploy from GitHub”, select repo.  
3. **Configure**:  

   * **Build command**: `pip install -r backend/requirements.txt`  
   * **Run command**: `gunicorn app.main:app -b 0.0.0.0:$PORT`  

4. **Add Variables** (same keys as Render).  

5. Railway will give you a URL like `https://sepnova-backend.up.railway.app`.

Both platforms will automatically restart the container if the process crashes, and they expose a public HTTPS endpoint that the frontend can call.

---
## 7️⃣ Deploy the **frontend** on a free platform

### 7.1 Vercel (recommended for Next.js)

1. **Install the Vercel CLI** (optional, but handy):

   ```bash
   npm i -g vercel
   ```

2. **Link the folder** (from the repo root):

   ```bash
   cd frontend
   vercel link   # follow the prompts, choose your existing project or create a new one
   ```

3. **Add environment variables** in the Vercel dashboard (Project → Settings → Environment Variables):

   | Key | Value |
   |-----|-------|
   | `NEXT_PUBLIC_SUPABASE_URL` | `https://abcdefg.supabase.co` |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `YOUR_ANON_KEY` |
   | `NEXT_PUBLIC_API_URL` | `https://sepnova-backend.onrender.com`  *(or your Railway URL)* |

4. **Deploy**:

   ```bash
   vercel --prod
   ```

   Vercel will give you a URL like `https://sepnova.vercel.app`.

### 7.2 Netlify (alternative)

1. Push the `frontend` folder to a GitHub repo (or use the existing one).  
2. Go to <https://netlify.com> → “New site from Git”.  
3. Choose your repo, set the **build command** to `npm run build` and the **publish directory** to `out` (Next.js automatically creates `out/` after `npm run build`).  
4. Add the same environment variables under **Site settings → Environment variables** (prefix them with `NEXT_PUBLIC_` if you want them exposed to the browser).  
5. Press **Deploy site**.

Both Vercel and Netlify will serve the static site over HTTPS and give you a public URL that can call the deployed backend.

---
## 8️⃣ End‑to‑end verification after deployment

| Action | URL / Command |
|--------|---------------|
| **Health check** (backend) | `https://sepnova-backend.onrender.com/health` – should return `200 OK` |
| **Swagger UI** | `https://sepnova-backend.onrender.com/docs` – list of all routes |
| **Simulate endpoint** (authenticated as intensivist) | Use a signed Supabase JWT or the test‑client method shown in the repo’s `README`; expect a JSON payload with 20 hourly entries, SHAP drivers, lead‑time info. |
| **Calibration endpoint** | `https://sepnova-backend.onrender.com/api/v1/ml/calibration` – returns Brier score + reliability table |
| **Frontend page** | Open `https://sepnova.vercel.app` (or your Netlify URL) → you should see the dark bedside monitor, the **Simulation** split‑view, and all role‑guarded API calls work (403 for unauthenticated users). |

If any of the above return errors, double‑check:

* The `DATABASE_URL` is correct and the DB reachable.  
* The model artifact `sepnova_model_v3.pkl` is present in the container (Render/Railway copy the `ml/artifacts/` folder, or set `MODEL_PATH` to an absolute path inside the service).  
* The `NEXT_PUBLIC_API_URL` points to the correct backend URL.  
* All required env vars are **exactly** as shown (case‑sensitive).

---
## 9️⃣ Quick “one‑liner” cheat‑sheet (copy‑paste)

```bash
# -------------------------------------------------
# 0️⃣ Prereqs (once)
# -------------------------------------------------
git install                # or your OS package manager
node -v                    # should be >=18
python -v                  # should be 3.12

# -------------------------------------------------
# 1️⃣ Clone & go
# -------------------------------------------------
git clone https://github.com/USER/SEPNOVA.git .
cd SEPNOVA

# -------------------------------------------------
# 2️⃣ Backend venv + deps
# -------------------------------------------------
python -m venv .venv
.venv\Scripts\activate      # Windows
# .venv/bin/activate        # macOS/Linux
pip install --upgrade pip
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env   # edit DATABASE_URL + MODEL_PATH

# -------------------------------------------------
# 3️⃣ Frontend deps + env
# -------------------------------------------------
cd frontend
npm install
cp .env.local.example .env.local   # add NEXT_PUBLIC_SUPABASE_URL + KEY

# -------------------------------------------------
# 4️⃣ Start both sides (two terminals)
# -------------------------------------------------
# Terminal A – backend
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8123

# Terminal B – frontend
cd frontend
npm run dev          # opens http://localhost:3000

# -------------------------------------------------
# 5️⃣ (optional) push to GitHub & deploy
# -------------------------------------------------
git remote add origin git@github.com:USER/SEPNOVA.git
git push -u origin main

# Render / Railway: set env vars, deploy.
# Vercel:   vercel --prod  (from frontend folder)
```

---
### 🎉 You’re all set!

* Run locally with the two‑terminal method.  
* Connect any PostgreSQL DB (Supabase is the easiest free option).  
* Deploy the backend to Render/Railway and the front‑end to Vercel/Netlify using the step‑by‑step commands above.  

If you hit any snag, consult the respective platform’s logs – they usually tell you which env var is missing or the model file can’t be found. Happy coding!