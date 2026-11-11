/**
 * RiskGauge — circular 0–100 risk arc. Colour follows the risk level, but the
 * numeric percentage and level chip always carry the same meaning in text.
 */
const R = 21;
const C = 2 * Math.PI * R;

export function RiskGauge({ score, level }: { score?: number | null; level?: string }) {
  const pct = Math.max(0, Math.min(1, score ?? 0));
  return (
    <div className="risk-gauge">
      <svg
        className="risk-gauge__svg"
        viewBox="0 0 52 52"
        role="img"
        aria-label={`Risk ${(pct * 100).toFixed(0)} percent, ${level ?? "low"}`}
      >
        <circle className="risk-gauge__track" cx="26" cy="26" r={R} />
        <circle
          className="risk-gauge__fill"
          cx="26"
          cy="26"
          r={R}
          strokeDasharray={C}
          strokeDashoffset={C * (1 - pct)}
          transform="rotate(-90 26 26)"
        />
        <text className="risk-gauge__num" x="26" y="27" textAnchor="middle">
          {(pct * 100).toFixed(0)}
        </text>
        <text className="risk-gauge__pct" x="26" y="36" textAnchor="middle">
          %
        </text>
      </svg>
      <span className="sr-only">Risk score {(pct * 100).toFixed(1)}%</span>
    </div>
  );
}
