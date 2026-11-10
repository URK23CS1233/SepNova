-- ============================================================
-- SepNova — patient_readings (long-format vital/lab readings)
-- Run in the Supabase SQL Editor AFTER database/schema.sql.
--
-- Stores one row per (patient, parameter, timestamp) so the v3 model can
-- aggregate the last 6 hours per parameter for prospective sepsis prediction.
-- Safe to re-run (idempotent).
-- ============================================================

-- Base table (created if it does not already exist).
CREATE TABLE IF NOT EXISTS patient_readings (
  id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  patient_id   TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  recorded_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Individual reading columns.
ALTER TABLE patient_readings ADD COLUMN IF NOT EXISTS parameter     varchar(50);
ALTER TABLE patient_readings ADD COLUMN IF NOT EXISTS value_numeric float8;
ALTER TABLE patient_readings ADD COLUMN IF NOT EXISTS unit          varchar(20);
ALTER TABLE patient_readings ADD COLUMN IF NOT EXISTS source        varchar(30) DEFAULT 'manual';

CREATE INDEX IF NOT EXISTS idx_readings_patient_param_ts
  ON patient_readings (patient_id, parameter, recorded_at DESC);

-- Row Level Security: backend uses the service_role key (bypasses RLS); clinical
-- roles may read. Policies are created only if missing so the script re-runs cleanly.
ALTER TABLE patient_readings ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies
                 WHERE tablename = 'patient_readings' AND policyname = 'service_all') THEN
    CREATE POLICY "service_all" ON patient_readings
      FOR ALL USING (auth.role() = 'service_role');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_policies
                 WHERE tablename = 'patient_readings' AND policyname = 'readings_read') THEN
    CREATE POLICY "readings_read" ON patient_readings
      FOR SELECT USING (auth.role() IN ('authenticated', 'service_role'));
  END IF;
END $$;

-- Optional: expose to Supabase Realtime (ignore error if already added).
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND schemaname = 'public' AND tablename = 'patient_readings'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE patient_readings;
  END IF;
END $$;
