"use client";
import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { ChatPanel } from "./ChatPanel";

// These paths are public — no sidebar/chat
const PUBLIC_PATHS = ["/", "/login", "/signup"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublic = PUBLIC_PATHS.some(
    (p) => pathname === p || (p !== "/" && pathname.startsWith(p))
  );

  if (isPublic) {
    return <>{children}</>;
  }

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-main">{children}</main>
      <ChatPanel />
    </div>
  );
}
