"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Alert } from "@/lib/api";
import { RiskBadge } from "@/components/RiskBadge";
import { Bell, CheckCircle, AlertTriangle } from "lucide-react";
import { cn, timeAgo } from "@/lib/utils";

export default function AlertsPage() {
  const [alerts, setAlerts]     = useState<Alert[]>([]);
  const [loading, setLoading]   = useState(true);
  const [showAcked, setShowAcked] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const a = await api.alerts.list(showAcked);
      setAlerts(a);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [showAcked]);

  async function acknowledge(id: string) {
    await api.alerts.acknowledge(id, "Clinician");
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  }

  return (
    <div className="al-page">
      <div className="al-header">
        <div>
          <h1 className="al-title">
            <Bell className="al-title__icon" />
            Alerts
          </h1>
          <p className="al-subtitle">
            {showAcked ? "Acknowledged" : "Unacknowledged"} clinical alerts
          </p>
        </div>
        <button
          onClick={() => setShowAcked(!showAcked)}
          className="btn btn--ghost"
        >
          {showAcked ? "Show Unacknowledged" : "Show Acknowledged"}
        </button>
      </div>

      {loading ? (
        <div className="al-list">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="al-skeleton" />
          ))}
        </div>
      ) : alerts.length === 0 ? (
        <div className="al-empty">
          <CheckCircle className="al-empty__icon" />
          <p className="al-empty__title">All clear — no {showAcked ? "acknowledged" : "active"} alerts</p>
        </div>
      ) : (
        <div className="al-list">
          {alerts.map((alert) => (
            <div
              key={alert.id}
              className={cn(
                "al-card",
                alert.severity === "critical" ? "al-card--critical" : "al-card--high"
              )}
            >
              <AlertTriangle
                className={cn(
                  "al-card__icon",
                  alert.severity === "critical" ? "al-card__icon--critical" : "al-card__icon--high"
                )}
              />
              <div className="al-card__body">
                <div className="al-card__row">
                  <Link
                    href={`/patient/${alert.patient_id}`}
                    className="al-card__patient"
                  >
                    {alert.patient_id}
                  </Link>
                  <RiskBadge
                    level={alert.severity === "critical" ? "critical" : "high"}
                    size="sm"
                  />
                  {alert.risk_score != null && (
                    <span className="al-card__score">
                      Score: {(alert.risk_score * 100).toFixed(0)}%
                    </span>
                  )}
                  <span className="al-card__time">{timeAgo(alert.created_at)}</span>
                </div>
                <p className="al-card__message">{alert.message}</p>
              </div>
              {!alert.is_acknowledged && (
                <button
                  onClick={() => acknowledge(alert.id)}
                  className="al-ack-btn"
                >
                  Acknowledge
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
