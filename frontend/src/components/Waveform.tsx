/**
 * Waveform — live-looking ECG / SpO2 sweep lines drawn as SVG.
 * Purely illustrative monitor traces; the numeric values are the real input.
 * Animation is disabled by the stylesheet under prefers-reduced-motion.
 */
const W = 300;
const H = 44;

function ecgTrace(seed: number): string {
  const points: string[] = ["M 0 28"];
  const beats = 3;
  for (let b = 0; b < beats; b++) {
    const x = 18 + b * 92 + (seed % 5);
    // P wave
    points.push(`Q ${x} 24 ${x + 8} 28`);
    // QRS complex
    points.push(`L ${x + 13} 30`);
    points.push(`L ${x + 17} 8`);
    points.push(`L ${x + 21} 36`);
    points.push(`L ${x + 26} 28`);
    // T wave
    points.push(`Q ${x + 36} 20 ${x + 46} 28`);
    points.push(`L ${x + 56} 28`);
  }
  points.push(`L ${W} 28`);
  return points.join(" ");
}

function spo2Trace(seed: number, value: number): string {
  const amplitude = Math.max(3, Math.min(12, (value - 80) * 0.45));
  const points: string[] = [];
  for (let x = 0; x <= W; x += 4) {
    const phase = (x / W) * Math.PI * 6 + seed * 0.2;
    const notch = Math.sin(phase * 2) * amplitude * 0.18;
    const y = 28 - Math.sin(phase) * amplitude - notch;
    points.push(`${x === 0 ? "M" : "L"} ${x} ${y.toFixed(1)}`);
  }
  return points.join(" ");
}

interface Props {
  kind: "ecg" | "spo2";
  label: string;
  value: number | null | undefined;
  unit: string;
  seed?: number;
}

export function Waveform({ kind, label, value, unit, seed = 1 }: Props) {
  const numeric = value ?? 0;
  const path = kind === "ecg" ? ecgTrace(seed) : spo2Trace(seed, numeric || 96);
  return (
    <div className={`wave wave--${kind}`}>
      <span className="wave__label">{label}</span>
      <span className="wave__value">
        {value == null ? "—" : Math.round(numeric)}
        <span className="wave__unit"> {unit}</span>
      </span>
      <svg className="wave__trace" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
        <path d={path} />
      </svg>
    </div>
  );
}
