-- ============================================================
-- SepNova — Authentication & RBAC Schema
-- Run AFTER schema.sql in your Supabase SQL Editor
-- ============================================================

-- ─────────────────────────────────────────────
-- 1. USER PROFILES (links auth.users → role)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_profiles (
  id          UUID    PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  full_name   TEXT    NOT NULL,
  role        TEXT    NOT NULL CHECK (role IN (
                'intensivist','surgeon','nurse',
                'anesthesiologist','lab_technician','admin'
              )),
  ward        TEXT,           -- nurses/anesthesiologists see only their ward
  employee_id TEXT    UNIQUE,
  is_active   BOOLEAN DEFAULT TRUE,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- 2. PATIENT ASSIGNMENTS
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS patient_assignments (
  id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  patient_id  TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role        TEXT NOT NULL,
  assigned_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (patient_id, user_id)
);

-- ─────────────────────────────────────────────
-- 3. AUDIT LOG (immutable append-only)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
  id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id     UUID REFERENCES auth.users(id),
  user_role   TEXT,
  action      TEXT NOT NULL,
  patient_id  TEXT,
  table_name  TEXT,
  record_id   TEXT,
  details     JSONB,
  ip_address  TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE RULE audit_log_no_update AS ON UPDATE TO audit_log DO INSTEAD NOTHING;
CREATE RULE audit_log_no_delete AS ON DELETE TO audit_log DO INSTEAD NOTHING;

-- ─────────────────────────────────────────────
-- 4. SURGICAL NOTES
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS surgical_notes (
  id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  patient_id  TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  surgeon_id  UUID REFERENCES auth.users(id),
  note_type   TEXT CHECK (note_type IN ('pre_op','intra_op','post_op','consult')),
  content     TEXT NOT NULL,
  procedure   TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- 5. ANESTHESIA RECORDS
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS anesthesia_records (
  id                  UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  patient_id          TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  anesthesiologist_id UUID REFERENCES auth.users(id),
  agent               TEXT,
  dose_mg             FLOAT,
  route               TEXT,
  airway_type         TEXT,
  etco2               FLOAT,
  fio2                FLOAT,
  recorded_at         TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- 6. MEDICATION ADMINISTRATION
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS medication_admin (
  id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  patient_id  TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  nurse_id    UUID REFERENCES auth.users(id),
  drug_name   TEXT NOT NULL,
  dose        TEXT,
  route       TEXT,
  indication  TEXT,
  admin_time  TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- 7. HELPER FUNCTIONS
-- ─────────────────────────────────────────────
CREATE OR REPLACE FUNCTION get_my_role()
RETURNS TEXT LANGUAGE sql SECURITY DEFINER AS $$
  SELECT role FROM user_profiles WHERE id = auth.uid();
$$;

CREATE OR REPLACE FUNCTION get_my_ward()
RETURNS TEXT LANGUAGE sql SECURITY DEFINER AS $$
  SELECT ward FROM user_profiles WHERE id = auth.uid();
$$;

-- ─────────────────────────────────────────────
-- 8. RLS POLICIES
-- ─────────────────────────────────────────────

-- user_profiles
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own_profile" ON user_profiles FOR SELECT USING (id = auth.uid());
CREATE POLICY "admin_all"   ON user_profiles FOR ALL   USING (get_my_role() = 'admin');
CREATE POLICY "service_all" ON user_profiles FOR ALL   USING (auth.role() = 'service_role');

-- patient_assignments
ALTER TABLE patient_assignments ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own_assign"  ON patient_assignments FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "admin_all"   ON patient_assignments FOR ALL   USING (get_my_role() IN ('admin','intensivist'));
CREATE POLICY "service_all" ON patient_assignments FOR ALL   USING (auth.role() = 'service_role');

-- audit_log
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "read_audit"   ON audit_log FOR SELECT USING (get_my_role() IN ('admin','intensivist'));
CREATE POLICY "insert_audit" ON audit_log FOR INSERT WITH CHECK (TRUE);
CREATE POLICY "service_all"  ON audit_log FOR ALL   USING (auth.role() = 'service_role');

-- surgical_notes
ALTER TABLE surgical_notes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "surgeon_read"  ON surgical_notes FOR SELECT USING (
  get_my_role() = 'intensivist' OR (get_my_role() = 'surgeon' AND surgeon_id = auth.uid())
);
CREATE POLICY "surgeon_write" ON surgical_notes FOR INSERT WITH CHECK (get_my_role() IN ('surgeon','intensivist'));
CREATE POLICY "service_all"   ON surgical_notes FOR ALL USING (auth.role() = 'service_role');

-- anesthesia_records
ALTER TABLE anesthesia_records ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anes_read"   ON anesthesia_records FOR SELECT USING (get_my_role() IN ('intensivist','anesthesiologist'));
CREATE POLICY "anes_write"  ON anesthesia_records FOR INSERT WITH CHECK (get_my_role() IN ('anesthesiologist','intensivist'));
CREATE POLICY "service_all" ON anesthesia_records FOR ALL USING (auth.role() = 'service_role');

-- medication_admin
ALTER TABLE medication_admin ENABLE ROW LEVEL SECURITY;
CREATE POLICY "med_read"    ON medication_admin FOR SELECT USING (get_my_role() IN ('intensivist','nurse'));
CREATE POLICY "med_write"   ON medication_admin FOR INSERT WITH CHECK (get_my_role() IN ('nurse','intensivist'));
CREATE POLICY "service_all" ON medication_admin FOR ALL USING (auth.role() = 'service_role');

-- patients (replace anon_read with role-scoped)
DROP POLICY IF EXISTS "anon_read" ON patients;
DROP POLICY IF EXISTS "service_role_all" ON patients;
CREATE POLICY "clinical_read" ON patients FOR SELECT USING (
  get_my_role() IN ('intensivist','surgeon','anesthesiologist','lab_technician') OR
  (get_my_role() = 'nurse' AND (ward = get_my_ward() OR get_my_ward() IS NULL)) OR
  auth.role() = 'service_role'
);
CREATE POLICY "service_all" ON patients FOR ALL USING (auth.role() = 'service_role');

-- vitals
DROP POLICY IF EXISTS "anon_read" ON vitals;
CREATE POLICY "vitals_read"  ON vitals FOR SELECT USING (get_my_role() IN ('intensivist','surgeon','nurse','anesthesiologist') OR auth.role() = 'service_role');
CREATE POLICY "vitals_write" ON vitals FOR INSERT WITH CHECK (get_my_role() IN ('nurse','intensivist') OR auth.role() = 'service_role');
CREATE POLICY "service_all"  ON vitals FOR ALL USING (auth.role() = 'service_role');

-- lab_results
DROP POLICY IF EXISTS "anon_read" ON lab_results;
CREATE POLICY "lab_read"    ON lab_results FOR SELECT USING (get_my_role() IN ('intensivist','surgeon','nurse','anesthesiologist','lab_technician') OR auth.role() = 'service_role');
CREATE POLICY "lab_write"   ON lab_results FOR INSERT WITH CHECK (get_my_role() IN ('lab_technician','intensivist') OR auth.role() = 'service_role');
CREATE POLICY "service_all" ON lab_results FOR ALL USING (auth.role() = 'service_role');

-- predictions (nurses see risk_level only — enforced in API layer)
DROP POLICY IF EXISTS "anon_read" ON predictions;
CREATE POLICY "pred_read"   ON predictions FOR SELECT USING (get_my_role() IN ('intensivist','surgeon','nurse','anesthesiologist') OR auth.role() = 'service_role');
CREATE POLICY "service_all" ON predictions FOR ALL USING (auth.role() = 'service_role');

-- alerts
DROP POLICY IF EXISTS "anon_read" ON alerts;
CREATE POLICY "alert_read"  ON alerts FOR SELECT USING (get_my_role() IN ('intensivist','surgeon','nurse','anesthesiologist') OR auth.role() = 'service_role');
CREATE POLICY "alert_ack"   ON alerts FOR UPDATE USING (get_my_role() IN ('intensivist','nurse'));
CREATE POLICY "service_all" ON alerts FOR ALL USING (auth.role() = 'service_role');

-- model_runs (intensivist only)
DROP POLICY IF EXISTS "anon_read" ON model_runs;
CREATE POLICY "intensivist_only" ON model_runs FOR SELECT USING (get_my_role() = 'intensivist' OR auth.role() = 'service_role');
CREATE POLICY "service_all"      ON model_runs FOR ALL USING (auth.role() = 'service_role');

-- ─────────────────────────────────────────────
-- 9. AUTO-CREATE PROFILE ON SIGNUP
-- ─────────────────────────────────────────────
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  INSERT INTO user_profiles (id, full_name, role)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.email),
    COALESCE(NEW.raw_app_meta_data->>'role', 'nurse')
  )
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- ─────────────────────────────────────────────
-- 10. REALTIME
-- (idempotent: skip tables already in the publication — `alerts` is added by
--  schema.sql, so a plain ADD would error and roll back this whole script)
-- ─────────────────────────────────────────────
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['medication_admin','anesthesia_records','surgical_notes','alerts']
  LOOP
    IF NOT EXISTS (
      SELECT 1 FROM pg_publication_tables
      WHERE pubname = 'supabase_realtime' AND schemaname = 'public' AND tablename = t
    ) THEN
      EXECUTE format('ALTER PUBLICATION supabase_realtime ADD TABLE %I', t);
    END IF;
  END LOOP;
END $$;
