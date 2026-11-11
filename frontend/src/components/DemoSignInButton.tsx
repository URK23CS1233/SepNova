"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PlayCircle } from "lucide-react";

export const DEMO_COOKIE = "sepnova_demo";

export function isDemoMode(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.localStorage.getItem("sepnova_demo") === "1" ||
    document.cookie.split(";").some((c) => c.trim().startsWith("sepnova_demo=1"))
  );
}

export function enterDemoMode() {
  window.localStorage.setItem("sepnova_demo", "1");
  document.cookie = "sepnova_demo=1; path=/; max-age=86400; SameSite=Lax";
}

export function exitDemoMode() {
  window.localStorage.removeItem("sepnova_demo");
  document.cookie = "sepnova_demo=; path=/; max-age=0; SameSite=Lax";
}

export function DemoSignInButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const handleClick = () => {
    setLoading(true);
    enterDemoMode();
    // Full page navigation so the middleware sees the fresh demo cookie.
    window.location.href = "/dashboard";
  };

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      className="flex items-center gap-2 px-8 py-4 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-white font-bold text-lg transition-all hover:scale-105 hover:shadow-2xl hover:shadow-emerald-500/40 disabled:opacity-60"
    >
      <PlayCircle className="h-5 w-5" />
      {loading ? "Entering demo…" : "Try Live Demo"}
    </button>
  );
}
