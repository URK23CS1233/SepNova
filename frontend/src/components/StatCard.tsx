import { cn } from "@/lib/utils";

interface Props {
  label: string;
  value: string | number;
  sub?: string;
  accent?: "red" | "orange" | "yellow" | "green" | "blue";
}

const ACCENT: Record<NonNullable<Props["accent"]>, string> = {
  red:    "stat-card--red",
  orange: "stat-card--orange",
  yellow: "stat-card--yellow",
  green:  "stat-card--green",
  blue:   "stat-card--blue",
};

export function StatCard({ label, value, sub, accent = "blue" }: Props) {
  return (
    <div className={cn("stat-card", ACCENT[accent])}>
      <p className="stat-card__label">{label}</p>
      <p className="stat-card__value">{value}</p>
      {sub && <p className="stat-card__sub">{sub}</p>}
    </div>
  );
}
