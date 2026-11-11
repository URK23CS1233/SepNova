"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Activity, LayoutDashboard, Bell, BarChart3, FlaskConical, Settings, LogOut, Lightbulb, PlayCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";

const ROLE_AVATAR: Record<string, string> = {
  intensivist:      "user-card__avatar--intensivist",
  surgeon:          "user-card__avatar--surgeon",
  nurse:            "user-card__avatar--nurse",
  anesthesiologist: "user-card__avatar--anesthesiologist",
  lab_technician:   "user-card__avatar--lab_technician",
  admin:            "user-card__avatar--admin",
};

const ALL_NAV = [
  { href: "/dashboard", label: "Ward Overview", icon: LayoutDashboard, roles: ["intensivist","surgeon","nurse","anesthesiologist"] },
  { href: "/simulate", label: "Simulation",    icon: PlayCircle,    roles: ["intensivist","surgeon","nurse","anesthesiologist"] },
  { href: "/alerts",   label: "Alerts",        icon: Bell,          roles: ["intensivist","surgeon","nurse","anesthesiologist"] },
  { href: "/labs",     label: "Lab Results",   icon: FlaskConical,  roles: ["intensivist","nurse","lab_technician","anesthesiologist","surgeon"] },
  { href: "/results",  label: "Model Results", icon: BarChart3,     roles: ["intensivist"] },
  { href: "/insights", label: "Insights",      icon: Lightbulb,     roles: ["intensivist","surgeon","nurse","anesthesiologist","admin"] },
  { href: "/admin",    label: "Admin Panel",   icon: Settings,      roles: ["admin"] },
];

export function Sidebar() {
  const path   = usePathname();
  const router = useRouter();
  const { profile, role, signOut } = useAuth();

  const NAV = ALL_NAV.filter((item) => !role || item.roles.includes(role));

  async function handleSignOut() {
    await signOut();
    router.replace("/");
  }

  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <div className="sidebar__brand-mark">
          <Activity className="h-5 w-5" />
        </div>
        <div>
          <div className="sidebar__title">SepNova</div>
          <p className="sidebar__subtitle">ICU Sepsis Monitor</p>
        </div>
      </div>

      <nav className="sidebar__nav">
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn("nav-link", path === href && "nav-link--active")}
          >
            <Icon className="nav-link__icon" />
            {label}
          </Link>
        ))}
      </nav>

      {profile && (
        <div className="sidebar__footer">
          <div className="user-card">
            <div className={cn("user-card__avatar", ROLE_AVATAR[role ?? "admin"])}>
              {profile.full_name?.charAt(0).toUpperCase() ?? "?"}
            </div>
            <div className="min-w-0 flex-1">
              <p className="user-card__name">{profile.full_name}</p>
              <p className="user-card__role">{role?.replace("_", " ")}</p>
            </div>
          </div>
          <button onClick={handleSignOut} className="signout-btn">
            <LogOut className="h-3.5 w-3.5" />
            Sign out
          </button>
        </div>
      )}
    </aside>
  );
}
