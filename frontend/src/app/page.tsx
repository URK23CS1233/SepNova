"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  Activity, Shield, Brain, Users, ChevronRight, ArrowRight,
  Zap, Eye, Clock, BarChart3, Heart, Lock, Star, CheckCircle
} from "lucide-react";

/* ─── Animated ECG SVG ────────────────────────────────────────────── */
function ECGLine({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 1200 120" preserveAspectRatio="none" className={className} fill="none">
      <path
        d="M0,60 L60,60 L80,60 L90,20 L100,100 L115,5 L130,115 L145,60 L160,60
           L220,60 L240,60 L250,20 L260,100 L275,5 L290,115 L305,60 L320,60
           L380,60 L400,60 L410,20 L420,100 L435,5 L450,115 L465,60 L480,60
           L540,60 L560,60 L570,20 L580,100 L595,5 L610,115 L625,60 L640,60
           L700,60 L720,60 L730,20 L740,100 L755,5 L770,115 L785,60 L800,60
           L860,60 L880,60 L890,20 L900,100 L915,5 L930,115 L945,60 L960,60
           L1020,60 L1040,60 L1050,20 L1060,100 L1075,5 L1090,115 L1105,60 L1200,60"
        stroke="url(#ecgGradient)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="animate-ecg"
      />
      <defs>
        <linearGradient id="ecgGradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%"   stopColor="#06b6d4" stopOpacity="0" />
          <stop offset="20%"  stopColor="#38bdf8" stopOpacity="1" />
          <stop offset="80%"  stopColor="#818cf8" stopOpacity="1" />
          <stop offset="100%" stopColor="#34d399" stopOpacity="0" />
        </linearGradient>
      </defs>
    </svg>
  );
}

/* ─── Particle background ─────────────────────────────────────────── */
function ParticleField() {
  const particles = Array.from({ length: 40 }, (_, i) => ({
    id: i,
    left: `${Math.random() * 100}%`,
    top:  `${Math.random() * 100}%`,
    size: Math.random() * 3 + 1,
    delay: `${Math.random() * 6}s`,
    duration: `${4 + Math.random() * 8}s`,
    opacity: Math.random() * 0.4 + 0.1,
  }));
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {particles.map((p) => (
        <div
          key={p.id}
          className="absolute rounded-full bg-sky-400"
          style={{
            left: p.left, top: p.top,
            width: p.size, height: p.size,
            opacity: p.opacity,
            animation: `particle-drift ${p.duration} ${p.delay} ease-in-out infinite`,
          }}
        />
      ))}
    </div>
  );
}

/* ─── Animated stat counter ───────────────────────────────────────── */
function Counter({ target, suffix = "", decimals = 0 }: { target: number; suffix?: string; decimals?: number }) {
  const [val, setVal] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const started = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && !started.current) {
        started.current = true;
        const duration = 1800;
        const start = Date.now();
        const tick = () => {
          const progress = Math.min((Date.now() - start) / duration, 1);
          const eased = 1 - Math.pow(1 - progress, 3);
          setVal(eased * target);
          if (progress < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      }
    }, { threshold: 0.5 });
    obs.observe(el);
    return () => obs.disconnect();
  }, [target]);

  return (
    <span ref={ref}>
      {val.toFixed(decimals)}{suffix}
    </span>
  );
}

/* ─── Scroll reveal hook ──────────────────────────────────────────── */
function useReveal() {
  useEffect(() => {
    const els = document.querySelectorAll(".reveal");
    const obs = new IntersectionObserver(
      (entries) => entries.forEach((e) => { if (e.isIntersecting) e.target.classList.add("visible"); }),
      { threshold: 0.12 }
    );
    els.forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, []);
}

/* ─── Live mini-dashboard mockup ──────────────────────────────────── */
function DashboardMockup() {
  const patients = [
    { id: "ICU-047", risk: "CRITICAL", score: 78, trend: "↑", color: "text-red-400" },
    { id: "ICU-031", risk: "HIGH",     score: 56, trend: "↑", color: "text-orange-400" },
    { id: "ICU-019", risk: "MEDIUM",   score: 34, trend: "→", color: "text-yellow-400" },
    { id: "ICU-052", risk: "LOW",      score: 12, trend: "↓", color: "text-emerald-400" },
  ];
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 2500);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="glass rounded-2xl p-5 w-full max-w-sm animate-float-slow shadow-2xl shadow-sky-900/30">
      {/* Header bar */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-sky-400" />
          <span className="text-white text-xs font-semibold">SepNova Live</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-emerald-400 text-xs">LIVE</span>
        </div>
      </div>
      {/* Patient rows */}
      <div className="space-y-2.5">
        {patients.map((p, i) => (
          <div
            key={p.id}
            className={`flex items-center justify-between rounded-lg px-3 py-2 transition-all duration-500
              ${i === tick % 4 ? "bg-white/10 ring-1 ring-white/20" : "bg-white/5"}`}
          >
            <div>
              <p className="text-white text-xs font-mono">{p.id}</p>
              <div className="h-1 w-20 mt-1 rounded-full bg-white/10 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-1000
                    ${p.risk === "CRITICAL" ? "bg-red-400" :
                      p.risk === "HIGH" ? "bg-orange-400" :
                      p.risk === "MEDIUM" ? "bg-yellow-400" : "bg-emerald-400"}`}
                  style={{ width: `${p.score}%` }}
                />
              </div>
            </div>
            <div className="text-right">
              <p className={`text-xs font-bold ${p.color}`}>{p.risk}</p>
              <p className="text-white/60 text-xs">{p.score}% {p.trend}</p>
            </div>
          </div>
        ))}
      </div>
      {/* SNS score panel */}
      <div className="mt-3 rounded-lg bg-gradient-to-r from-sky-900/60 to-indigo-900/60 p-3">
        <p className="text-xs text-sky-300 font-medium">SepNova Score (ICU-047)</p>
        <div className="flex items-end gap-2 mt-1">
          <span className="text-2xl font-bold text-white">0.78</span>
          <span className="text-xs text-red-400 mb-1 font-semibold animate-pulse">CRITICAL</span>
        </div>
        <div className="flex gap-1 mt-2">
          {[["ML", 43], ["qSOFA", 25], ["ΔSOFA", 10]].map(([label, w]) => (
            <div key={label as string} className="flex-1">
              <p className="text-xs text-white/40 mb-0.5">{label}</p>
              <div className="h-1 rounded-full bg-white/10">
                <div className="h-full rounded-full bg-sky-400" style={{ width: `${w as number}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ─── Main Landing Page ───────────────────────────────────────────── */
export default function LandingPage() {
  useReveal();
  const [navScrolled, setNavScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setNavScrolled(window.scrollY > 40);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-white overflow-x-hidden">

      {/* ── Sticky Nav ── */}
      <nav className={`fixed top-0 inset-x-0 z-50 transition-all duration-300
        ${navScrolled ? "glass-dark py-3 shadow-xl" : "bg-transparent py-5"}`}>
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-sky-500 flex items-center justify-center animate-glow">
              <Activity className="h-4.5 w-4.5 text-white" style={{height:18,width:18}} />
            </div>
            <span className="text-lg font-bold tracking-tight">SepNova</span>
          </div>
          <div className="flex items-center gap-4">
            <Link href="#features" className="text-sm text-slate-400 hover:text-white transition-colors hidden sm:block">
              Features
            </Link>
            <Link href="#roles" className="text-sm text-slate-400 hover:text-white transition-colors hidden sm:block">
              Roles
            </Link>
            <Link href="/login"
              className="text-sm text-slate-300 hover:text-white transition-colors px-4 py-1.5 rounded-full border border-white/20 hover:border-white/40">
              Sign In
            </Link>
            <Link href="/signup"
              className="text-sm font-semibold bg-sky-500 hover:bg-sky-400 text-white px-4 py-1.5 rounded-full transition-all hover:shadow-lg hover:shadow-sky-500/30">
              Get Access
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="relative min-h-screen flex items-center overflow-hidden">
        {/* Gradient orbs */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] rounded-full bg-sky-600/20 blur-[120px] animate-float-slow" />
          <div className="absolute bottom-1/4 right-1/4 w-[400px] h-[400px] rounded-full bg-indigo-600/20 blur-[120px]" style={{animation:"float-slow 8s 2s ease-in-out infinite"}} />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-emerald-600/10 blur-[150px]" />
        </div>

        {/* Particle field */}
        <ParticleField />

        {/* ECG line */}
        <div className="absolute bottom-28 left-0 right-0 h-24 opacity-30">
          <ECGLine className="w-full h-full" />
        </div>

        <div className="relative max-w-7xl mx-auto px-6 pt-24 pb-16 w-full">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            {/* Left: copy */}
            <div>
              {/* Badge */}
              <div className="inline-flex items-center gap-2 rounded-full border border-sky-500/40 bg-sky-500/10 px-4 py-1.5 text-sm text-sky-300 mb-6 animate-fade-in">
                <span className="h-1.5 w-1.5 rounded-full bg-sky-400 animate-pulse" />
                IEEE Xplore · ICCDA3 2026 · Salalah, Oman
              </div>

              <h1 className="text-5xl sm:text-6xl font-extrabold leading-tight mb-6 animate-fade-in-up">
                Catch Sepsis<br />
                <span className="text-gradient">Before It Strikes</span>
              </h1>

              <p className="text-lg text-slate-400 leading-relaxed mb-8 animate-fade-in-up" style={{animationDelay:"0.15s"}}>
                SepNova's novel ensemble ML model predicts sepsis onset <strong className="text-white">up to 6 hours earlier</strong> than traditional clinical triggers — with a composite score that fuses AI probability, qSOFA, and SOFA velocity into a single actionable alert.
              </p>

              <div className="flex flex-wrap gap-4 mb-10 animate-fade-in-up" style={{animationDelay:"0.25s"}}>
                <Link href="/signup"
                  className="flex items-center gap-2 px-6 py-3 rounded-xl bg-sky-500 hover:bg-sky-400 text-white font-semibold transition-all hover:scale-105 hover:shadow-xl hover:shadow-sky-500/30">
                  Request Access
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link href="/login"
                  className="flex items-center gap-2 px-6 py-3 rounded-xl border border-white/20 hover:border-white/40 text-white font-semibold transition-all hover:bg-white/5">
                  Sign In
                  <ChevronRight className="h-4 w-4" />
                </Link>
              </div>

              {/* Trust badges */}
              <div className="flex flex-wrap gap-4 animate-fade-in-up" style={{animationDelay:"0.35s"}}>
                {[
                  { icon: Shield, text: "HIPAA Compliant" },
                  { icon: Lock, text: "JWT + RLS Security" },
                  { icon: Star, text: "AUROC 0.895" },
                ].map(({ icon: Icon, text }) => (
                  <div key={text} className="flex items-center gap-1.5 text-xs text-slate-400">
                    <Icon className="h-3.5 w-3.5 text-sky-400" />
                    {text}
                  </div>
                ))}
              </div>
            </div>

            {/* Right: live dashboard mockup */}
            <div className="flex justify-center lg:justify-end animate-slide-right">
              <DashboardMockup />
            </div>
          </div>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 animate-bounce-sub">
          <span className="text-xs text-slate-500">Scroll to explore</span>
          <div className="h-8 w-px bg-gradient-to-b from-slate-500 to-transparent" />
        </div>
      </section>

      {/* ── Stats ── */}
      <section className="py-20 relative">
        <div className="absolute inset-0 bg-gradient-to-r from-sky-950/40 via-indigo-950/40 to-sky-950/40" />
        <div className="relative max-w-7xl mx-auto px-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-8">
            {[
              { label: "AUROC Score",      target: 0.895, suffix: "",  decimals: 3, sub: "vs 0.712 qSOFA-only" },
              { label: "Hours Earlier",    target: 6,     suffix: "h", decimals: 0, sub: "than clinical triggers" },
              { label: "Specificity",      target: 91,    suffix: "%", decimals: 0, sub: "minimising false alarms" },
              { label: "Clinical Roles",   target: 6,     suffix: "",  decimals: 0, sub: "role-scoped access" },
            ].map(({ label, target, suffix, decimals, sub }, i) => (
              <div key={label} className={`reveal delay-${i + 1} text-center`}>
                <div className="text-4xl font-black text-gradient mb-1">
                  <Counter target={target} suffix={suffix} decimals={decimals} />
                </div>
                <p className="text-sm font-semibold text-white mb-1">{label}</p>
                <p className="text-xs text-slate-500">{sub}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section id="features" className="py-24 max-w-7xl mx-auto px-6">
        <div className="text-center mb-16 reveal">
          <div className="inline-block px-3 py-1 rounded-full bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 text-xs font-semibold mb-4">
            NOVEL CONTRIBUTIONS
          </div>
          <h2 className="text-4xl font-bold text-white mb-4">
            Four reasons SepNova is <span className="text-gradient">research-ready</span>
          </h2>
          <p className="text-slate-400 max-w-xl mx-auto">
            Each feature represents a genuine technical novelty, designed to advance the state of AI-assisted sepsis prediction.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          {[
            {
              icon: BarChart3,
              color: "sky",
              badge: "NOVEL #1",
              title: "SepNova Composite Score",
              desc: "A novel fusion formula — SNS = 0.55×P_ML + 0.25×P_qSOFA + 0.20×V_SOFA — fusing probabilistic AI with bedside clinical scoring and SOFA deterioration velocity into a single, interpretable risk number.",
              points: ["No prior work fuses all three signals", "Velocity captures deterioration rate", "Threshold-tuned per risk level"],
              delay: 1,
            },
            {
              icon: Clock,
              color: "indigo",
              badge: "NOVEL #2",
              title: "Multi-Horizon Prediction",
              desc: "Three parallel models — 3h, 6h, and 12h — each with optimised decision thresholds and SMOTE ratios. Clinicians get graded alerts: 12h advisory, 6h warning, 3h critical.",
              points: ["Horizon-specific threshold tuning", "Alarm fatigue management built-in", "Early-warning → imminent stratification"],
              delay: 2,
            },
            {
              icon: Eye,
              color: "emerald",
              badge: "NOVEL #3",
              title: "Counterfactual Explainability",
              desc: "For every high-risk patient, SepNova computes the minimum clinically actionable change needed to move to the next lower risk level. \"If Lactate drops 4.3 → 2.1 mmol/L, risk falls 72% → 44%.\"",
              points: ["Binary-search counterfactual engine", "Only actionable clinical features", "Narrative explanations per patient"],
              delay: 3,
            },
            {
              icon: Users,
              color: "rose",
              badge: "NOVEL #4",
              title: "Demographic Fairness Audit",
              desc: "Real-time AUROC monitoring across age bands (<50, 50–65, 65–80, >80) and gender. Flags disparities automatically — aligned with FDA AI/ML-Based SaMD guidance on bias monitoring.",
              points: ["Runtime fairness, not just offline", "Equalized opportunity criterion", "FDA SaMD guideline-aligned"],
              delay: 4,
            },
          ].map(({ icon: Icon, color, badge, title, desc, points, delay }) => (
            <div key={title}
              className={`reveal delay-${delay} card-hover glass rounded-2xl p-6 group`}>
              <div className="flex items-start gap-4 mb-4">
                <div className={`h-10 w-10 rounded-xl flex items-center justify-center flex-shrink-0
                  bg-${color}-500/20 group-hover:bg-${color}-500/30 transition-colors`}>
                  <Icon className={`h-5 w-5 text-${color}-400`} />
                </div>
                <div>
                  <span className={`text-xs font-bold text-${color}-400 tracking-widest`}>{badge}</span>
                  <h3 className="text-base font-bold text-white mt-0.5">{title}</h3>
                </div>
              </div>
              <p className="text-sm text-slate-400 leading-relaxed mb-4">{desc}</p>
              <ul className="space-y-1.5">
                {points.map((pt) => (
                  <li key={pt} className="flex items-center gap-2 text-xs text-slate-300">
                    <CheckCircle className="h-3.5 w-3.5 text-emerald-400 flex-shrink-0" />
                    {pt}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      {/* ── How it works ── */}
      <section className="py-20 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-slate-900/50 to-transparent" />
        <div className="relative max-w-7xl mx-auto px-6">
          <div className="text-center mb-16 reveal">
            <h2 className="text-4xl font-bold mb-4">How SepNova works</h2>
            <p className="text-slate-400 max-w-lg mx-auto">From raw ICU vitals to a life-saving alert in seconds.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 relative">
            {/* Connecting line */}
            <div className="hidden md:block absolute top-8 left-1/3 right-1/3 h-px bg-gradient-to-r from-sky-500 via-indigo-500 to-emerald-500 z-0" />

            {[
              { step: "01", icon: Heart, color: "sky",    title: "Ingest ICU Data",      desc: "Vitals, labs, and clinical observations are continuously ingested from bedside monitors and the Supabase real-time database." },
              { step: "02", icon: Brain, color: "indigo", title: "ML Ensemble Analysis",  desc: "XGBoost + LightGBM weighted ensemble processes 130+ features. SOFA and qSOFA are computed in parallel. SNS is calculated." },
              { step: "03", icon: Zap,   color: "emerald",title: "Role-Scoped Clinical Action", desc: "Each clinical role sees only the data relevant to them — with explainability, counterfactuals, and horizon-graded alerts." },
            ].map(({ step, icon: Icon, color, title, desc }, i) => (
              <div key={step} className={`reveal delay-${i + 1} relative z-10 text-center`}>
                <div className={`inline-flex h-16 w-16 rounded-2xl items-center justify-center mb-5
                  bg-${color}-500/20 border border-${color}-500/30 ring-4 ring-slate-950`}>
                  <Icon className={`h-7 w-7 text-${color}-400`} />
                </div>
                <div className={`text-xs font-black text-${color}-500 mb-2 tracking-widest`}>STEP {step}</div>
                <h3 className="text-lg font-bold text-white mb-3">{title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Clinical Roles ── */}
      <section id="roles" className="py-24 max-w-7xl mx-auto px-6">
        <div className="text-center mb-16 reveal">
          <div className="inline-block px-3 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs font-semibold mb-4">
            ROLE-BASED ACCESS CONTROL
          </div>
          <h2 className="text-4xl font-bold mb-4">Built for every member of the ICU team</h2>
          <p className="text-slate-400 max-w-xl mx-auto">
            Each clinical role gets a personalised view — only the data they need, enforced at 4 layers: Next.js middleware, FastAPI, Postgres RLS, and column masking.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            { emoji: "👨‍⚕️", role: "Intensivist",      color: "sky",    access: "Full patient view · All ML scores · Fairness audit · Admin insights" },
            { emoji: "🔪",   role: "Surgeon",          color: "green",  access: "Surgical vitals · Coagulation labs · Surgical notes · Risk timeline" },
            { emoji: "💊",   role: "Nurse",            color: "pink",   access: "Bedside vitals · Basic labs · Medication admin · Alerts management" },
            { emoji: "😴",   role: "Anesthesiologist", color: "purple", access: "ABG · Haemodynamics · Anaesthesia records · Ventilator data" },
            { emoji: "🧪",   role: "Lab Technician",   color: "orange", access: "Lab result entry · Trend charts · Result verification only" },
            { emoji: "⚙️",   role: "Admin",            color: "slate",  access: "User management · Audit log · Invite clinicians · Role assignment" },
          ].map(({ emoji, role, color, access }, i) => (
            <div key={role}
              className={`reveal delay-${(i % 3) + 1} card-hover glass rounded-2xl p-5 group cursor-default`}>
              <div className="flex items-center gap-3 mb-3">
                <span className="text-2xl">{emoji}</span>
                <div>
                  <p className="font-semibold text-white">{role}</p>
                  <div className={`h-0.5 w-8 rounded-full bg-${color}-400 mt-1 group-hover:w-full transition-all duration-500`} />
                </div>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">{access}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Security strip ── */}
      <section className="py-16 border-y border-white/5">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex flex-wrap justify-center gap-10">
            {[
              { icon: Shield, label: "HIPAA Compliant",    sub: "End-to-end audit logging" },
              { icon: Lock,   label: "JWT + Supabase RLS", sub: "4-layer access enforcement" },
              { icon: Eye,    label: "Immutable Audit Log", sub: "Every action recorded" },
              { icon: Star,   label: "IEEE Research",       sub: "ICCDA3 2026 submission" },
            ].map(({ icon: Icon, label, sub }) => (
              <div key={label} className="flex items-center gap-3 reveal">
                <div className="h-10 w-10 rounded-xl bg-sky-500/15 flex items-center justify-center">
                  <Icon className="h-5 w-5 text-sky-400" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">{label}</p>
                  <p className="text-xs text-slate-500">{sub}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="py-32 relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute inset-0 bg-gradient-to-br from-sky-950 via-slate-950 to-indigo-950 animate-gradient-x" />
          <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-sky-500 to-transparent" />
          <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-indigo-500 to-transparent" />
          {/* Decorative rings */}
          {[1, 2, 3].map((n) => (
            <div key={n} className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-sky-500/10"
              style={{ width: n * 250, height: n * 250, animationDelay: `${n * 0.5}s` }} />
          ))}
        </div>

        <div className="relative max-w-2xl mx-auto px-6 text-center">
          <div className="h-16 w-16 rounded-2xl bg-sky-500 flex items-center justify-center mx-auto mb-8 animate-glow animate-float">
            <Activity className="h-8 w-8 text-white" />
          </div>
          <h2 className="text-5xl font-extrabold text-white mb-6 reveal">
            Ready to transform<br /><span className="text-gradient">ICU care?</span>
          </h2>
          <p className="text-slate-400 text-lg mb-10 reveal delay-1">
            Join SepNova and give your clinical team the AI advantage they need to save more lives.
          </p>
          <div className="flex flex-wrap gap-4 justify-center reveal delay-2">
            <Link href="/signup"
              className="flex items-center gap-2 px-8 py-4 rounded-xl bg-sky-500 hover:bg-sky-400 text-white font-bold text-lg transition-all hover:scale-105 hover:shadow-2xl hover:shadow-sky-500/40">
              Request Access
              <ArrowRight className="h-5 w-5" />
            </Link>
            <Link href="/login"
              className="flex items-center gap-2 px-8 py-4 rounded-xl border border-white/20 hover:border-white/40 text-white font-semibold text-lg transition-all hover:bg-white/5">
              Sign In
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="py-8 border-t border-white/5">
        <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="h-6 w-6 rounded bg-sky-500 flex items-center justify-center">
              <Activity className="h-3.5 w-3.5 text-white" />
            </div>
            <span className="text-sm font-semibold text-white">SepNova</span>
            <span className="text-xs text-slate-600">· Early Sepsis Prediction Platform</span>
          </div>
          <p className="text-xs text-slate-600">
            Research project · ICCDA3 2026 · Data Science & Analytics Track
          </p>
        </div>
      </footer>
    </div>
  );
}
