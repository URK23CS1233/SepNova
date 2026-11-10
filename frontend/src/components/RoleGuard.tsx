"use client";
import { useAuth, UserRole } from "@/contexts/AuthContext";

interface Props {
  roles: UserRole[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

/**
 * Renders children only if the current user has one of the specified roles.
 * Use this to hide UI sections from unauthorized roles.
 * NOTE: This is a UI convenience — actual enforcement is in the backend + RLS.
 */
export function RoleGuard({ roles, children, fallback = null }: Props) {
  const { hasRole, loading } = useAuth();
  if (loading) return null;
  return hasRole(...roles) ? <>{children}</> : <>{fallback}</>;
}
