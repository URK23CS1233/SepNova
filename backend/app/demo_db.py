"""In-memory Supabase-compatible client used in demo mode (Bearer demo).

Implements just enough of the postgrest query-builder API used by the routers
so that DB-dependent pages render realistic data without a real Supabase.
"""
from datetime import datetime, timezone, timedelta
import uuid

from .demo_data import (
    PATIENTS, RISK, VITALS, list_patients, get_patient, dashboard_summary,
    get_vitals, get_labs, get_predictions, ALERTS, alert_stats,
)


def _now():
    return datetime.now(timezone.utc)


class _Result:
    def __init__(self, data=None, count=None):
        self.data = data if data is not None else []
        self.count = count


class _Query:
    def __init__(self, table_name):
        self.table_name = table_name
        self._filters = []
        self._order = None
        self._desc = False
        self._limit = None
        self._single = False
        self._maybe_single = False
        self._count = None
        self._update = None
        self._insert = None

    # --- chainable filters ---
    def select(self, cols="*", count=None):
        self._count = count
        return self

    def eq(self, col, val):
        self._filters.append((col, "eq", val))
        return self

    def is_(self, col, val):
        self._filters.append((col, "is", val))
        return self

    def not_(self):
        # returns a proxy that flips; simplified: store a flag
        self._not = True
        return self

    # postgrest style: .not_.is_(col, val)
    # handled below via attribute

    def order(self, col, desc=False):
        self._order = col
        self._desc = desc
        return self

    def limit(self, n):
        self._limit = n
        return self

    def single(self):
        self._single = True
        return self

    def maybe_single(self):
        self._maybe_single = True
        return self

    def insert(self, row):
        self._insert = row
        return self

    def update(self, row):
        self._update = row
        return self

    def execute(self):
        data = self._run()
        if self._single or self._maybe_single:
            if isinstance(data, list):
                data = data[0] if data else None
        if self._count == "exact":
            cnt = len(data) if isinstance(data, list) else (1 if data else 0)
            return _Result(data, cnt)
        return _Result(data)

    def _run(self):
        tn = self.table_name

        if self._insert is not None:
            return [self._insert]

        if self._update is not None:
            # acknowledge alert no-op
            return [{"status": "ok"}]

        # ----- patients -----
        if tn == "patients":
            rows = []
            for p in PATIENTS:
                row = {
                    "id": str(uuid.uuid4()),
                    "patient_id": p["patient_id"],
                    "age": p["age"],
                    "gender": p["gender"],
                    "hosp_adm_time": p["hosp_adm_time"],
                    "icu_los": p["icu_los"],
                    "ward": p["ward"],
                    "status": p["status"],
                    "created_at": (_now() - timedelta(days=1)).isoformat(),
                }
                rows.append(row)
            rows = self._apply_filters(rows)
            if self._order:
                rows = sorted(rows, key=lambda r: r.get(self._order), reverse=self._desc)
            if self._limit:
                rows = rows[: self._limit]
            return rows

        # ----- vitals -----
        if tn == "vitals":
            # aggregate across patients if no filter; else single patient trajectory
            pids = [f[2] for f in self._filters if f[0] == "patient_id" and f[1] == "eq"]
            if pids:
                pid = pids[0]
                rows = get_vitals(pid)
                # normalize to db shape
                out = []
                for v in rows:
                    out.append({
                        "id": v.get("id", str(uuid.uuid4())),
                        "patient_id": pid,
                        "hour": v["hour"],
                        "hr": v.get("hr"),
                        "o2sat": v.get("o2sat"),
                        "temp": v.get("temp"),
                        "sbp": v.get("sbp"),
                        "map": v.get("map"),
                        "dbp": v.get("dbp"),
                        "resp": v.get("resp"),
                        "recorded_at": v.get("recorded_at"),
                    })
                rows = out
            else:
                rows = []
            rows = self._apply_filters(rows)
            if self._order:
                rows = sorted(rows, key=lambda r: r.get(self._order, 0), reverse=self._desc)
            if self._limit:
                rows = rows[: self._limit]
            return rows

        # ----- lab_results -----
        if tn == "lab_results":
            pids = [f[2] for f in self._filters if f[0] == "patient_id" and f[1] == "eq"]
            if pids:
                rows = get_labs(pids[0])
            else:
                rows = []
            rows = self._apply_filters(rows)
            if self._order:
                rows = sorted(rows, key=lambda r: r.get(self._order, 0), reverse=self._desc)
            if self._limit:
                rows = rows[: self._limit]
            return rows

        # ----- predictions -----
        if tn == "predictions":
            pids = [f[2] for f in self._filters if f[0] == "patient_id" and f[1] == "eq"]
            if pids:
                rows = get_predictions(pids[0])
            else:
                # all patients
                rows = []
                for p in PATIENTS:
                    rows.extend(get_predictions(p["patient_id"]))
            # apply sepsis_label filter (not_.is_ null) -> none have labels, so empty
            # detect not_.is_ sepsis_label null
            for f in self._filters:
                if f[0] == "sepsis_label":
                    return []
            rows = self._apply_filters(rows)
            if self._order:
                # predicted_at sort
                rows = sorted(rows, key=lambda r: r.get(self._order, ""), reverse=self._desc)
            if self._limit:
                rows = rows[: self._limit]
            return rows

        # ----- alerts -----
        if tn == "alerts":
            ack_filter = None
            sev_filter = None
            for f in self._filters:
                if f[0] == "is_acknowledged":
                    ack_filter = f[2]
                if f[0] == "severity":
                    sev_filter = f[2]
            rows = list_alerts if False else None
            from .demo_data import list_alerts as _la
            rows = _la(acknowledged=ack_filter if ack_filter is not None else False,
                       severity=sev_filter, limit=self._limit or 50)
            # if acknowledged filter not specified, return all? default False
            if ack_filter is None:
                from .demo_data import ALERTS as _A
                rows = list(_A)
                if sev_filter:
                    rows = [a for a in rows if a["severity"] == sev_filter]
                rows = rows[: (self._limit or 50)]
            rows = self._apply_filters(rows)
            if self._order:
                rows = sorted(rows, key=lambda r: r.get(self._order, ""), reverse=self._desc)
            if self._limit:
                rows = rows[: self._limit]
            return rows

        # ----- model_runs -----
        if tn == "model_runs":
            return [{
                "id": str(uuid.uuid4()),
                "run_name": "sepnova_v3",
                "model_type": "ensemble",
                "auroc": 0.912,
                "auprc": 0.74,
                "sensitivity": 0.88,
                "specificity": 0.82,
                "f1_score": 0.80,
                "threshold": 0.2078,
                "n_patients": 8,
                "n_sepsis": 2,
                "ran_at": _now().isoformat(),
            }]

        # ----- user_profiles / audit_log / surgical_notes / etc -----
        if tn in ("user_profiles", "audit_log", "surgical_notes", "anesthesia_records",
                   "medication_admin", "patient_readings"):
            return []

        return []

    def _apply_filters(self, rows):
        for col, op, val in self._filters:
            if op == "eq":
                rows = [r for r in rows if r.get(col) == val]
            elif op == "is":
                # not_.is_ handled by _not flag; simplified: treat is null
                pass
        # handle not_.is_ sepsis_label null -> empty (already returned [])
        return rows

    # support .not_ attribute chain
    @property
    def not_(self):
        # return self to allow .not_.is_()
        return self


class DemoSupabaseClient:
    def table(self, name):
        return _Query(name)


def get_demo_db():
    return DemoSupabaseClient()
