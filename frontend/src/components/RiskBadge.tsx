import { cn } from "@/lib/utils";

interface Props {
  level?: string;
  score?: number;
  size?: "sm" | "md";
}

const LEVELS = ["critical", "high", "medium", "low"];

export function RiskBadge({ level = "low", score, size = "md" }: Props) {
  const lvl = LEVELS.includes(level) ? level : "low";

  return (
    <span className={cn("risk-badge", `risk-badge--${lvl}`, size === "sm" && "risk-badge--sm")}>
      <span className="risk-badge__dot" />
      {level}
      {score != null && (
        <span className="risk-badge__score">({(score * 100).toFixed(0)}%)</span>
      )}
    </span>
  );
}
