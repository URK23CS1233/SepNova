"use client";
import { useState } from "react";
import Link from "next/link";
import { Activity, ArrowLeft, Eye, EyeOff, ShieldCheck, CheckCircle, User, Mail, Lock, Building2, Stethoscope } from "lucide-react";
import { supabase } from "@/lib/supabase";

const ROLES = [
  { value: "intensivist",      label: "Intensivist",       emoji: "👨‍⚕️" },
  { value: "surgeon",          label: "Surgeon",            emoji: "🔪" },
  { value: "nurse",            label: "Nurse",              emoji: "💊" },
  { value: "anesthesiologist", label: "Anesthesiologist",   emoji: "😴" },
  { value: "lab_technician",   label: "Lab Technician",     emoji: "🧪" },
];

export default function SignupPage() {
  const [step, setStep]         = useState<"form" | "success">("form");
  const [fullName, setFullName] = useState("");
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [hospital, setHospital] = useState("");
  const [role, setRole]         = useState("");
  const [showPw, setShowPw]     = useState(false);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!fullName || !email || !password || !hospital || !role) {
      setError("Please fill in all fields.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setLoading(true);
    setError(null);

    try {
      const { error: signUpError } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: { full_name: fullName, hospital, requested_role: role },
        },
      });
      if (signUpError) throw new Error(signUpError.message);
      setStep("success");
    } catch (err: any) {
      setError(err.message ?? "Sign-up failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 right-0 w-[600px] h-[600px] rounded-full bg-indigo-600/15 blur-[140px]" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] rounded-full bg-sky-600/15 blur-[120px]" />
      </div>

      <div className="relative w-full max-w-md animate-fade-in-up">
        {/* Back link */}
        <Link href="/" className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors text-sm mb-8">
          <ArrowLeft className="h-4 w-4" />
          Back to home
        </Link>

        {step === "success" ? (
          /* ── Success state ── */
          <div className="glass rounded-3xl p-10 text-center animate-scale-in">
            <div className="h-20 w-20 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-6 animate-glow">
              <CheckCircle className="h-10 w-10 text-emerald-400" />
            </div>
            <h2 className="text-2xl font-bold text-white mb-3">Access Requested!</h2>
            <p className="text-slate-400 text-sm leading-relaxed mb-8">
              Your account has been created. An administrator will review and activate your access. You'll be notified at <strong className="text-white">{email}</strong>.
            </p>
            <div className="flex flex-col gap-3">
              <Link href="/login"
                className="w-full py-3 rounded-xl bg-sky-500 hover:bg-sky-400 text-white font-semibold text-sm transition-all hover:shadow-lg hover:shadow-sky-500/30">
                Go to Sign In
              </Link>
              <Link href="/"
                className="w-full py-3 rounded-xl border border-white/10 hover:border-white/20 text-slate-400 hover:text-white text-sm transition-colors">
                Return to Home
              </Link>
            </div>
          </div>
        ) : (
          /* ── Form ── */
          <>
            <div className="text-center mb-8">
              <div className="inline-flex h-14 w-14 rounded-2xl bg-sky-500 items-center justify-center mb-4 animate-glow">
                <Activity className="h-7 w-7 text-white" />
              </div>
              <h1 className="text-2xl font-bold text-white">Join SepNova</h1>
              <p className="text-slate-400 text-sm mt-1">Request access for your clinical team</p>
            </div>

            <div className="glass rounded-3xl p-8 shadow-2xl">
              {error && (
                <div className="mb-5 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Full name */}
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">Full Name</label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
                    <input
                      type="text" value={fullName} onChange={(e) => setFullName(e.target.value)}
                      placeholder="Dr. Jane Smith" required autoComplete="name"
                      className="w-full pl-10 pr-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm placeholder:text-slate-600
                        focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all"
                    />
                  </div>
                </div>

                {/* Email */}
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">Hospital Email</label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
                    <input
                      type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@hospital.org" required autoComplete="email"
                      className="w-full pl-10 pr-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm placeholder:text-slate-600
                        focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all"
                    />
                  </div>
                </div>

                {/* Password */}
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">Password</label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
                    <input
                      type={showPw ? "text" : "password"} value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Min. 8 characters" required autoComplete="new-password"
                      className="w-full pl-10 pr-10 py-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm placeholder:text-slate-600
                        focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all"
                    />
                    <button type="button" onClick={() => setShowPw(!showPw)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
                      {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                  {/* Password strength indicator */}
                  <div className="flex gap-1 mt-2">
                    {[8, 12, 16].map((threshold, i) => (
                      <div key={threshold} className="flex-1 h-1 rounded-full overflow-hidden bg-white/10">
                        <div className={`h-full rounded-full transition-all duration-300 ${
                          password.length >= threshold
                            ? i === 0 ? "bg-red-400" : i === 1 ? "bg-yellow-400" : "bg-emerald-400"
                            : ""
                        }`} style={{ width: password.length >= threshold ? "100%" : "0%" }} />
                      </div>
                    ))}
                  </div>
                </div>

                {/* Hospital */}
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">Hospital / Institution</label>
                  <div className="relative">
                    <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
                    <input
                      type="text" value={hospital} onChange={(e) => setHospital(e.target.value)}
                      placeholder="City General Hospital" required
                      className="w-full pl-10 pr-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm placeholder:text-slate-600
                        focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all"
                    />
                  </div>
                </div>

                {/* Role selector */}
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">
                    <Stethoscope className="inline h-3.5 w-3.5 mr-1 -mt-0.5" />
                    Clinical Role
                  </label>
                  <div className="grid grid-cols-1 gap-2">
                    {ROLES.map((r) => (
                      <button
                        key={r.value}
                        type="button"
                        onClick={() => setRole(r.value)}
                        className={`flex items-center gap-3 px-4 py-2.5 rounded-xl border text-sm text-left transition-all
                          ${role === r.value
                            ? "border-sky-500 bg-sky-500/10 text-white"
                            : "border-white/10 bg-white/5 text-slate-400 hover:border-white/20 hover:text-white"}`}
                      >
                        <span className="text-base">{r.emoji}</span>
                        {r.label}
                        {role === r.value && <CheckCircle className="h-4 w-4 text-sky-400 ml-auto" />}
                      </button>
                    ))}
                  </div>
                </div>

                <button
                  type="submit" disabled={loading || !role}
                  className="w-full py-3 rounded-xl bg-sky-500 hover:bg-sky-400 disabled:opacity-50 disabled:cursor-not-allowed
                    text-white font-semibold text-sm transition-all hover:shadow-lg hover:shadow-sky-500/30 mt-2"
                >
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <span className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Creating account…
                    </span>
                  ) : "Request Access"}
                </button>
              </form>

              <div className="mt-5 flex items-start gap-2 p-3 rounded-xl bg-white/5 border border-white/5">
                <ShieldCheck className="h-4 w-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-slate-500 leading-relaxed">
                  Accounts require admin approval. Your role will be verified before access is granted. All sessions are HIPAA-compliant and fully audited.
                </p>
              </div>
            </div>

            <p className="text-center text-sm text-slate-500 mt-6">
              Already have access?{" "}
              <Link href="/login" className="text-sky-400 hover:text-sky-300 transition-colors font-medium">
                Sign in
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
