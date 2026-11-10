import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function riskColor(level?: string): string {
  switch (level) {
    case "critical": return "text-red-700 bg-red-50 border-red-200";
    case "high":     return "text-orange-700 bg-orange-50 border-orange-200";
    case "medium":   return "text-yellow-700 bg-yellow-50 border-yellow-200";
    default:         return "text-green-700 bg-green-50 border-green-200";
  }
}

export function riskDot(level?: string): string {
  switch (level) {
    case "critical": return "bg-red-600 animate-pulse";
    case "high":     return "bg-orange-500";
    case "medium":   return "bg-yellow-400";
    default:         return "bg-green-500";
  }
}

export function pct(val?: number): string {
  if (val == null) return "—";
  return `${(val * 100).toFixed(1)}%`;
}

export function score(val?: number): string {
  if (val == null) return "—";
  return val.toFixed(3);
}

export function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1)  return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}
