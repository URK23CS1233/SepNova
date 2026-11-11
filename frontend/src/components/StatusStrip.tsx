/**
 * StatusStrip — top monitor bar: ward, UTC clock, alarm count and a
 * silence-alarm control that requires explicit confirmation.
 */
"use client";

import { useEffect, useState } from "react";
import { Activity, Bell, Clock3, ShieldAlert, VolumeX } from "lucide-react";

interface Props {
  ward: string;
  alarmCount: number;
  criticalCount?: number;
  simulated?: boolean;
}

const SILENCE_SECONDS = 120;

export function StatusStrip({ ward, alarmCount, criticalCount = 0, simulated = false }: Props) {
  const [now, setNow] = useState<Date | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [silencedFor, setSilencedFor] = useState(0);

  useEffect(() => {
    setNow(new Date());
    const timer = window.setInterval(() => {
      setNow(new Date());
      setSilencedFor((s) => (s > 0 ? s - 1 : 0));
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  const utc = now
    ? `${now.toISOString().slice(11, 19)} UTC`
    : "--:--:-- UTC";

  const hot = criticalCount > 0 || alarmCount > 0;

  return (
    <div className="status-strip">
      <div className="status-strip__brand">
        <Activity size={16} aria-hidden="true" />
        SepNova
      </div>

      <div className="status-strip__item">
        Ward <strong>{ward}</strong>
      </div>

      <div className="status-strip__item">
        <Clock3 size={13} aria-hidden="true" />
        <strong>{utc}</strong>
      </div>

      <div className="status-strip__item">
        <Bell size={13} aria-hidden="true" />
        Alarms{" "}
        <span className={`alarm-count${hot ? " alarm-count--hot" : ""}`}>
          {String(alarmCount).padStart(2, "0")}
        </span>
      </div>

      {simulated && (
        <div className="status-strip__item">
          <ShieldAlert size={13} aria-hidden="true" />
          <strong style={{ color: "var(--amber, #f2b632)" }}>SIMULATED</strong>
        </div>
      )}

      <div className="status-strip__spacer" />

      <button
        type="button"
        className={`silence-btn${silencedFor > 0 ? " silence-btn--active" : ""}`}
        onClick={() => setConfirming(true)}
        disabled={silencedFor > 0}
      >
        <VolumeX size={14} aria-hidden="true" />
        {silencedFor > 0 ? `Silenced ${silencedFor}s` : "Silence alarms"}
      </button>

      {silencedFor > 0 && (
        <div className="silenced-banner" role="status">
          Alarm audio silenced for {silencedFor}s — visual alarms remain active.
        </div>
      )}

      {confirming && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="silence-title">
            <h2 className="modal__title" id="silence-title">
              Silence audible alarms?
            </h2>
            <p className="modal__body">
              This will silence audible alarms for {SILENCE_SECONDS} seconds. Visual alarms,
              the alarm count and the pulsing critical border remain active. Confirm only if
              a clinician is at the bedside.
            </p>
            <div className="modal__actions">
              <button
                type="button"
                className="monitor-btn"
                onClick={() => setConfirming(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="monitor-btn monitor-btn--danger"
                onClick={() => {
                  setSilencedFor(SILENCE_SECONDS);
                  setConfirming(false);
                }}
              >
                <VolumeX size={14} aria-hidden="true" />
                Confirm silence
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
