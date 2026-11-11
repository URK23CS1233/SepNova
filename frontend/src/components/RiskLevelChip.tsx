/**
 * RiskLevelChip — text + icon + colour, so risk is never conveyed by colour alone.
 */
import { ShieldCheck, TriangleAlert, Siren, CircleAlert } from "lucide-react";

const ICONS: Record<string, typeof ShieldCheck> = {
  low: ShieldCheck,
  medium: TriangleAlert,
  high: CircleAlert,
  critical: Siren,
};

export function RiskLevelChip({ level = "low" }: { level?: string }) {
  const lvl = ICONS[level] ? level : "low";
  const Icon = ICONS[lvl];
  return (
    <span className="level-chip" aria-label={`Risk level ${lvl}`}>
      <span className="level-chip__dot" aria-hidden="true" />
      <Icon size={12} aria-hidden="true" />
      {lvl}
    </span>
  );
}
