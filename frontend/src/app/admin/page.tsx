"use client";
import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";
import { useAuth } from "@/contexts/AuthContext";
import { Settings, UserPlus, Shield, CheckCircle, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface UserProfile {
  id:          string;
  full_name:   string;
  role:        string;
  ward?:       string;
  employee_id?: string;
  is_active:   boolean;
  created_at:  string;
}

const ROLES = ["intensivist","surgeon","nurse","anesthesiologist","lab_technician","admin"];
const ROLE_SELECT: Record<string, string> = {
  intensivist: "ad-role-select--intensivist",
  surgeon: "ad-role-select--surgeon",
  nurse: "ad-role-select--nurse",
  anesthesiologist: "ad-role-select--anesthesiologist",
  lab_technician: "ad-role-select--lab_technician",
  admin: "ad-role-select--admin",
};

export default function AdminPage() {
  const { session } = useAuth();
  const [users, setUsers]     = useState<UserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab]         = useState<"users"|"invite"|"audit">("users");

  // Invite form
  const [email, setEmail]         = useState("");
  const [fullName, setFullName]   = useState("");
  const [role, setRole]           = useState("nurse");
  const [ward, setWard]           = useState("");
  const [inviting, setInviting]   = useState(false);
  const [inviteMsg, setInviteMsg] = useState<{type:"ok"|"err"; text:string} | null>(null);

  // Audit log
  const [audit, setAudit] = useState<unknown[]>([]);

  async function authHeaders() {
    const tok = session?.access_token;
    return { "Content-Type": "application/json", "Authorization": `Bearer ${tok}` };
  }

  async function loadUsers() {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/admin/users`, {
      headers: await authHeaders(),
    });
    if (res.ok) setUsers(await res.json());
    setLoading(false);
  }

  async function loadAudit() {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/admin/audit-log?limit=50`, {
      headers: await authHeaders(),
    });
    if (res.ok) setAudit(await res.json());
  }

  useEffect(() => { loadUsers(); }, []);
  useEffect(() => { if (tab === "audit") loadAudit(); }, [tab]);

  async function changeRole(userId: string, newRole: string) {
    await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/admin/users/${userId}`, {
      method: "PATCH",
      headers: await authHeaders(),
      body: JSON.stringify({ role: newRole }),
    });
    await loadUsers();
  }

  async function toggleActive(userId: string, current: boolean) {
    if (current) {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/admin/users/${userId}`, {
        method: "DELETE",
        headers: await authHeaders(),
      });
    } else {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/admin/users/${userId}`, {
        method: "PATCH",
        headers: await authHeaders(),
        body: JSON.stringify({ is_active: true }),
      });
    }
    await loadUsers();
  }

  async function inviteUser(e: React.FormEvent) {
    e.preventDefault();
    setInviting(true);
    setInviteMsg(null);
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/admin/users/invite`, {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify({ email, full_name: fullName, role, ward: ward || null }),
    });
    if (res.ok) {
      setInviteMsg({ type: "ok", text: `Invitation sent to ${email}` });
      setEmail(""); setFullName(""); setWard("");
      await loadUsers();
    } else {
      const err = await res.json();
      setInviteMsg({ type: "err", text: err.detail ?? "Invite failed" });
    }
    setInviting(false);
  }

  return (
    <div className="page">
      <div className="ad-header">
        <div className="ad-header__mark">
          <Shield className="h-6 w-6" />
        </div>
        <div>
          <h1 className="ad-header__title">Admin Panel</h1>
          <p className="ad-header__sub">Manage users, invitations, and audit activity</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="ad-tabs">
        {(["users","invite","audit"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={cn("ad-tab", tab === t && "ad-tab--active")}
          >
            {t === "invite" ? "Invite User" : t === "audit" ? "Audit Log" : "Users"}
          </button>
        ))}
      </div>

      {/* Users */}
      {tab === "users" && (
        <div className="ad-card">
          <table className="ad-table">
            <thead className="ad-table__head">
              <tr>
                {["Name","Role","Ward","Status","Actions"].map(h => (
                  <th key={h} className="ad-table__th">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="ad-table__body">
              {users.map((u) => (
                <tr key={u.id} className={cn("ad-row", !u.is_active && "ad-row--inactive")}>
                  <td className="ad-cell">
                    <p className="ad-name">{u.full_name}</p>
                    <p className="ad-name__id">{u.id.slice(0, 8)}…</p>
                  </td>
                  <td className="ad-cell">
                    <select
                      value={u.role}
                      onChange={(e) => changeRole(u.id, e.target.value)}
                      className={cn("ad-role-select", ROLE_SELECT[u.role])}
                    >
                      {ROLES.map((r) => <option key={r} value={r}>{r.replace("_"," ")}</option>)}
                    </select>
                  </td>
                  <td className="ad-cell ad-cell--muted">{u.ward ?? "—"}</td>
                  <td className="ad-cell">
                    {u.is_active
                      ? <span className="ad-status ad-status--active"><CheckCircle className="h-3.5 w-3.5" />Active</span>
                      : <span className="ad-status ad-status--inactive"><XCircle className="h-3.5 w-3.5" />Inactive</span>
                    }
                  </td>
                  <td className="ad-cell">
                    <button onClick={() => toggleActive(u.id, u.is_active)}
                      className="ad-action"
                    >
                      {u.is_active ? "Deactivate" : "Reactivate"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Invite */}
      {tab === "invite" && (
        <div className="ad-form-wrap">
          <form onSubmit={inviteUser} className="ad-form">
            <h2 className="ad-form__title">
              <UserPlus className="h-4 w-4" /> Invite new user
            </h2>
            {inviteMsg && (
              <div className={cn("ad-alert", inviteMsg.type === "ok" ? "ad-alert--ok" : "ad-alert--err")}>
                {inviteMsg.text}
              </div>
            )}
            {[
              { label: "Hospital email", type: "email", val: email, set: setEmail, required: true },
              { label: "Full name", type: "text", val: fullName, set: setFullName, required: true },
              { label: "Ward (optional)", type: "text", val: ward, set: setWard, required: false },
            ].map(({ label, type, val, set, required }) => (
              <div key={label}>
                <label className="ad-field__label">{label}</label>
                <input type={type} value={val} onChange={(e) => set(e.target.value)} required={required}
                  className="ad-input"
                />
              </div>
            ))}
            <div>
              <label className="ad-field__label">Role</label>
              <select value={role} onChange={(e) => setRole(e.target.value)}
                className="ad-input"
              >
                {ROLES.map((r) => <option key={r} value={r}>{r.replace("_"," ")}</option>)}
              </select>
            </div>
            <button type="submit" disabled={inviting}
              className="ad-submit"
            >
              {inviting ? "Sending…" : "Send invitation"}
            </button>
          </form>
        </div>
      )}

      {/* Audit log */}
      {tab === "audit" && (
        <div className="ad-card ad-card--scroll">
          <table className="ad-table ad-table--xs">
            <thead className="ad-table__head ad-table__head--sticky">
              <tr>
                {["Time","User","Role","Action","Patient","Details"].map(h => (
                  <th key={h} className="ad-table__th">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="ad-table__body">
              {(audit as Record<string, unknown>[]).map((row, i) => (
                <tr key={i} className="ad-row">
                  <td className="ad-cell ad-cell--faint ad-cell--nowrap">
                    {new Date(row.created_at as string).toLocaleString()}
                  </td>
                  <td className="ad-cell ad-cell--mono">{(row.user_id as string)?.slice(0,8)}…</td>
                  <td className="ad-cell capitalize">{(row.user_role as string)?.replace("_"," ")}</td>
                  <td className="ad-cell ad-cell--action">{row.action as string}</td>
                  <td className="ad-cell ad-cell--muted">{(row.patient_id as string) ?? "—"}</td>
                  <td className="ad-cell ad-cell--details">
                    {row.details ? JSON.stringify(row.details) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
