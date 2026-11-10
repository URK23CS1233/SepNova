"use client";
import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { supabase } from "@/lib/supabase";
import type { Session, User } from "@supabase/supabase-js";

export type UserRole =
  | "intensivist"
  | "surgeon"
  | "nurse"
  | "anesthesiologist"
  | "lab_technician"
  | "admin";

interface UserProfile {
  id:         string;
  full_name:  string;
  role:       UserRole;
  ward?:      string;
  employee_id?: string;
  is_active:  boolean;
}

interface AuthContextValue {
  session:  Session | null;
  user:     User | null;
  profile:  UserProfile | null;
  role:     UserRole | null;
  loading:  boolean;
  signIn:   (email: string, password: string) => Promise<string | null>;
  signOut:  () => Promise<void>;
  hasRole:  (...roles: UserRole[]) => boolean;
}

const AuthContext = createContext<AuthContextValue>({} as AuthContextValue);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession]   = useState<Session | null>(null);
  const [profile, setProfile]   = useState<UserProfile | null>(null);
  const [loading, setLoading]   = useState(true);

  async function fetchProfile(userId: string) {
    const { data } = await supabase
      .from("user_profiles")
      .select("*")
      .eq("id", userId)
      .single();
    if (data) setProfile(data as UserProfile);
  }

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      if (session?.user) fetchProfile(session.user.id);
      setLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (_event, session) => {
        setSession(session);
        if (session?.user) {
          await fetchProfile(session.user.id);
        } else {
          setProfile(null);
        }
        setLoading(false);
      }
    );

    return () => subscription.unsubscribe();
  }, []);

  async function signIn(email: string, password: string): Promise<string | null> {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    return error?.message ?? null;
  }

  async function signOut() {
    await supabase.auth.signOut();
    setProfile(null);
  }

  function hasRole(...roles: UserRole[]): boolean {
    return profile?.role ? roles.includes(profile.role) : false;
  }

  return (
    <AuthContext.Provider
      value={{
        session,
        user: session?.user ?? null,
        profile,
        role: profile?.role ?? null,
        loading,
        signIn,
        signOut,
        hasRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
