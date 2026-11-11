"use client";
import { Suspense, useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Activity, Eye, EyeOff, ShieldCheck, ArrowLeft, Lock, Mail } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

/* Mini ECG SVG in the background */
function BgECG() {
  return (
    <svg viewBox="0 0 1200 120" preserveAspectRatio="none" className="absolute inset-0 w-full h-full opacity-10" fill="none">
      <path
        d="M0,60 L80,60 L95,60 L105,25 L115,95 L128,5 L142,115 L155,60 L180,60
           L320,60 L335,60 L345,25 L355,95 L368,5 L382,115 L395,60 L420,60
           L580,60 L595,60 L605,25 L615,95 L628,5 L642,115 L655,60 L680,60
           L840,60 L855,60 L865,25 L875,95 L888,5 L902,115 L915,60 L940,60
           L1100,60 L1115,60 L1125,25 L1135,95 L1148,5 L1162,115 L1175,60 L1200,60"
        stroke="url(#loginECG)"
        strokeWidth="2"
        strokeLinecap="round"
        className="animate-ecg"
      />
      <defs>
        <linearGradient id="loginECG" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%"   stopColor="#0ea5e9" stopOpacity="0" />
          <stop offset="30%"  stopColor="#38bdf8" stopOpacity="1" />
          <stop offset="70%"  stopColor="#818cf8" stopOpacity="1" />
          <stop offset="100%" stopColor="#34d399" stopOpacity="0" />
        </linearGradient>
      </defs>
    </svg>
  );
}

function LoginContent() {
  const { signIn, session } = useAuth();
  const router      = useRouter();
  const params      = useSearchParams();

  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw]     = useState(false);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(
    params.get("error") === "deactivated"
      ? "Your account has been deactivated. Contact your administrator."
      : null
  );

  useEffect(() => {
    if (session) router.replace(params.get("redirect") ?? "/dashboard");
  }, [session]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email || !password) return;
    setLoading(true);
    setError(null);
    const err = await signIn(email, password);
    if (err) {
      setError(err);
      setLoading(false);
    } else {
      router.replace(params.get("redirect") ?? "/dashboard");
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Animated background */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/4 left-1/3 w-[500px] h-[500px] rounded-full bg-sky-600/15 blur-[130px] animate-float-slow" />
        <div className="absolute bottom-1/3 right-1/4 w-[350px] h-[350px] rounded-full bg-indigo-600/15 blur-[110px]" style={{animation:"float-slow 7s 1s ease-in-out infinite"}} />
      </div>

      {/* ECG lines - subtle background */}
      <div className="absolute bottom-16 left-0 right-0 h-28">
        <BgECG />
      </div>
      <div className="absolute top-16 left-0 right-0 h-20 rotate-180 opacity-50">
        <BgECG />
      </div>

      <div className="relative w-full max-w-sm animate-fade-in-up">
        {/* Back link */}
        <Link href="/" className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors text-sm mb-8">
          <ArrowLeft className="h-4 w-4" />
          Back to home
        </Link>

        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex h-16 w-16 rounded-2xl bg-sky-500 items-center justify-center mb-4 animate-glow">
            <Activity className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">Welcome back</h1>
          <p className="text-slate-400 text-sm mt-1">Sign in to your SepNova portal</p>
        </div>

        {/* Card */}
        <div className="glass rounded-3xl p-8 shadow-2xl shadow-black/40">
          {error && (
            <div className="mb-5 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm animate-fade-in">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Email */}
            <div className="group">
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Hospital Email</label>
              <div className="relative">
                <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 group-focus-within:text-sky-400 transition-colors" />
                <input
                  type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email" required placeholder="you@hospital.org"
                  className="w-full pl-10 pr-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm
                    placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent
                    focus:bg-white/8 transition-all"
                />
              </div>
            </div>

            {/* Password */}
            <div className="group">
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Password</label>
              <div className="relative">
                <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 group-focus-within:text-sky-400 transition-colors" />
                <input
                  type={showPw ? "text" : "password"} value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password" required placeholder="••••••••"
                  className="w-full pl-10 pr-12 py-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm
                    placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent
                    focus:bg-white/8 transition-all"
                />
                <button type="button" onClick={() => setShowPw(!showPw)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors">
                  {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit" disabled={loading}
              className="w-full py-3.5 rounded-xl bg-sky-500 hover:bg-sky-400 disabled:opacity-50 disabled:cursor-not-allowed
                text-white font-semibold text-sm transition-all hover:shadow-lg hover:shadow-sky-500/30 hover:scale-[1.01]
                active:scale-[0.99] mt-2"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Authenticating…
                </span>
              ) : "Sign In"}
            </button>
          </form>

          {/* HIPAA notice */}
          <div className="mt-5 flex items-start gap-2.5 p-3 rounded-xl bg-emerald-500/8 border border-emerald-500/15">
            <ShieldCheck className="h-4 w-4 text-emerald-400 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-slate-500 leading-relaxed">
              All sessions are encrypted, fully audited, and HIPAA-compliant. Unauthorised access is prohibited and logged.
            </p>
          </div>
        </div>

        <p className="text-center text-sm text-slate-500 mt-6">
          Need access?{" "}
          <Link href="/signup" className="text-sky-400 hover:text-sky-300 transition-colors font-medium">
            Request an account
          </Link>
        </p>
        <p className="text-center text-xs text-slate-600 mt-2">
          Contact your IT administrator for login issues.
        </p>
      </div>
    </div>
  );
}

// useSearchParams() must sit inside a Suspense boundary for static prerender.
export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-950" />}>
      <LoginContent />
    </Suspense>
  );
}
