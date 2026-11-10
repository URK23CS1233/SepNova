-- ============================================================
-- SepNova — Supabase Database Schema
-- Run this in your Supabase SQL Editor (Dashboard → SQL Editor)
-- ============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─────────────────────────────────────────────
-- 1. PATIENTS
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS patients (
  id              UUID    DEFAULT gen_random_uuid() PRIMARY KEY,
  patient_id      TEXT    UNIQUE NOT NULL,          -- e.g. "P-00042"
  age             INTEGER,
  gender          SMALLINT CHECK (gender IN (0,1)), -- 0=F, 1=M
  hosp_adm_time   FLOAT,                            -- hours before ICU admission
  icu_los         INTEGER,                           -- ICU length of stay (hours)
  ward            TEXT    DEFAULT 'ICU-A',
  status          TEXT    DEFAULT 'active'
                          CHECK (status IN ('active','discharged','deceased')),
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- 2. VITALS (time series, one row per hour)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vitals (
  id          UUID    DEFAULT gen_random_uuid() PRIMARY KEY,
  patient_id  TEXT    NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  hour        INTEGER NOT NULL,   -- ICU hour (1-indexed)
  hr          FLOAT,              -- Heart Rate
  o2sat       FLOAT,              -- O2 Saturation
  temp        FLOAT,              -- Temperature (°C)
  sbp         FLOAT,              -- Systolic BP
  map         FLOAT,              -- Mean Arterial Pressure
  dbp         FLOAT,              -- Diastolic BP
  resp        FLOAT,              -- Respiratory Rate
  recorded_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (patient_id, hour)
);

-- ─────────────────────────────────────────────
-- 3. LAB RESULTS (time series)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS lab_results (
  id              UUID    DEFAULT gen_random_uuid() PRIMARY KEY,
  patient_id      TEXT    NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  hour            INTEGER NOT NULL,
  lactate         FLOAT,
  wbc             FLOAT,
  creatinine      FLOAT,
  bilirubin_total FLOAT,
  bilirubin_direct FLOAT,
  platelets       FLOAT,
  glucose         FLOAT,
  hgb             FLOAT,
  hct             FLOAT,
  potassium       FLOAT,
  sodium          FLOAT,
  ph              FLOAT,
  paco2           FLOAT,
  hco3            FLOAT,
  base_excess     FLOAT,
  ptt             FLOAT,
  fibrinogen      FLOAT,
  troponin_i      FLOAT,
  ast             FLOAT,
  bun             FLOAT,
  calcium         FLOAT,
  recorded_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (patient_id, hour)
);

-- ─────────────────────────────────────────────
-- 4. PREDICTIONS (one row per prediction run)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS predictions (
  id              UUID    DEFAULT gen_random_uuid() PRIMARY KEY,
  patient_id      TEXT    NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  risk_score      FLOAT   NOT NULL CHECK (risk_score BETWEEN 0 AND 1),
  risk_level      TEXT    NOT NULL CHECK (risk_level IN ('low','medium','high','critical')),
  sepsis_label    SMALLINT,                         -- 1=sepsis, 0=no sepsis (ground truth if known)
  xgb_score       FLOAT,
  lgb_score       FLOAT,
  model_version   TEXT    DEFAULT 'v1.0',
  predicted_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- 5. MODEL RUNS (training/evaluation records)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS model_runs (
  id              UUID    DEFAULT gen_random_uuid() PRIMARY KEY,
  run_name        TEXT,
  model_type      TEXT,           -- 'XGBoost','LightGBM','Ensemble', etc.
  auroc           FLOAT,
  auprc           FLOAT,
  sensitivity     FLOAT,
  specificity     FLOAT,
  f1_score        FLOAT,
  threshold       FLOAT,
  n_patients      INTEGER,
  n_sepsis        INTEGER,
  parameters      JSONB,
  ran_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- 6. ALERTS
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alerts (
  id              UUID    DEFAULT gen_random_uuid() PRIMARY KEY,
  patient_id      TEXT    NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  alert_type      TEXT    NOT NULL,   -- 'sepsis_risk','vital_critical','lab_critical'
  severity        TEXT    NOT NULL CHECK (severity IN ('warning','critical')),
  message         TEXT    NOT NULL,
  risk_score      FLOAT,
  is_acknowledged BOOLEAN DEFAULT FALSE,
  acknowledged_by TEXT,
  acknowledged_at TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- INDEXES
-- ─────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_vitals_patient      ON vitals(patient_id);
CREATE INDEX IF NOT EXISTS idx_vitals_hour         ON vitals(patient_id, hour);
CREATE INDEX IF NOT EXISTS idx_labs_patient        ON lab_results(patient_id);
CREATE INDEX IF NOT EXISTS idx_predictions_patient ON predictions(patient_id);
CREATE INDEX IF NOT EXISTS idx_predictions_time    ON predictions(predicted_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_patient      ON alerts(patient_id);
CREATE INDEX IF NOT EXISTS idx_alerts_unacked      ON alerts(is_acknowledged) WHERE is_acknowledged = FALSE;

-- ─────────────────────────────────────────────
-- REAL-TIME (enable for live dashboard updates)
-- ─────────────────────────────────────────────
ALTER PUBLICATION supabase_realtime ADD TABLE predictions;
ALTER PUBLICATION supabase_realtime ADD TABLE alerts;
ALTER PUBLICATION supabase_realtime ADD TABLE vitals;

-- ─────────────────────────────────────────────
-- ROW LEVEL SECURITY (basic — expand per auth needs)
-- ─────────────────────────────────────────────
ALTER TABLE patients    ENABLE ROW LEVEL SECURITY;
ALTER TABLE vitals      ENABLE ROW LEVEL SECURITY;
ALTER TABLE lab_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_runs  ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts      ENABLE ROW LEVEL SECURITY;

-- Allow all for service_role (backend), read-only anon for frontend
CREATE POLICY "service_role_all" ON patients    FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "anon_read"        ON patients    FOR SELECT USING (TRUE);

CREATE POLICY "service_role_all" ON vitals      FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "anon_read"        ON vitals      FOR SELECT USING (TRUE);

CREATE POLICY "service_role_all" ON lab_results FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "anon_read"        ON lab_results FOR SELECT USING (TRUE);

CREATE POLICY "service_role_all" ON predictions FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "anon_read"        ON predictions FOR SELECT USING (TRUE);

CREATE POLICY "service_role_all" ON model_runs  FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "anon_read"        ON model_runs  FOR SELECT USING (TRUE);

CREATE POLICY "service_role_all" ON alerts      FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "anon_read"        ON alerts      FOR SELECT USING (TRUE);
