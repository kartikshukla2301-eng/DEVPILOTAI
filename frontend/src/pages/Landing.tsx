import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight, BookOpenText, Bug, Check, ChevronDown, Cpu, FileText, Gauge, GitPullRequestArrow, Lock, MessageSquareCode,
  ScanSearch, ShieldCheck, Sparkles, Upload,
} from "lucide-react";
import { Logo } from "../components/layout/AppLayout";
import { Button, StatusChip } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { LANGUAGES, LANG_COLORS } from "../lib/constants";
import { cn } from "../lib/utils";

const FEATURES = [
  { icon: ScanSearch, title: "Intelligent Code Review", tag: "Core engine", desc: "Bugs, code quality, security and performance findings with severity, line numbers, fixes and a 0–100 health score. Python uses AST, Ruff, Bandit and Radon." },
  { icon: Bug, title: "Debugging Assistant", tag: "Root cause", desc: "Paste a stack trace. DevPilot classifies the error, finds the crash line and proposes a patch. Mechanical Python fixes are re-parsed to check they work." },
  { icon: BookOpenText, title: "Code Explainer", tag: "Learning", desc: "Purpose, line-by-line walkthrough, functions, variables, detected algorithm and Big-O estimates at beginner, intermediate or advanced level." },
  { icon: Gauge, title: "Optimizer & Doc Generator", tag: "Productivity", desc: "Safe rewrites with a before/after diff (your original is never overwritten), plus downloadable Markdown documentation." },
];

const STEPS = [
  { icon: Upload, title: "Paste or upload code", desc: "Drop a file or paste a snippet in the Monaco editor. Seven languages are supported." },
  { icon: Cpu, title: "Static analysis runs", desc: "Language analyzers parse your code without executing it. Optional AI review adds clearly labelled suggestions." },
  { icon: GitPullRequestArrow, title: "Fix with confidence", desc: "Jump to each finding in the editor, compare suggested code side by side and export the report." },
];

const FAQ = [
  ["Does DevPilot run my code?", "No. Code is only parsed (Python AST, Ruff, Bandit, node --check, gofmt). It is never executed, and temporary files are deleted immediately after analysis."],
  ["Do I need an AI API key?", "No. Every module works in local rule-based mode. If the server has an OpenAI-compatible key configured, you can switch AI on per run. AI findings are always labelled separately from static findings."],
  ["Can static analysis find every bug?", "No tool can. Static analysis uses heuristics and pattern matching, so it can miss real problems and occasionally report false positives. Treat results as a strong second pair of eyes, not a guarantee."],
  ["Where is my data stored?", "In the MongoDB database configured for your deployment (local or Atlas). Every review belongs to your account, and you can export or delete any record or your whole account at any time."],
];

function ProductPreview() {
  return (
    <div className="relative mx-auto mt-14 max-w-5xl">
      <div className="pointer-events-none absolute -inset-x-10 -top-10 h-64 rounded-full bg-accent/20 blur-[120px]" />
      <div className="glass relative overflow-hidden rounded-2xl">
        <div className="flex items-center justify-between border-b border-border bg-surface-2/80 px-4 py-2.5">
          <div className="flex items-center gap-3">
            <div className="flex gap-1.5"><span className="h-3 w-3 rounded-full bg-[#ff5f57]" /><span className="h-3 w-3 rounded-full bg-[#febc2e]" /><span className="h-3 w-3 rounded-full bg-[#28c840]" /></div>
            <span className="font-mono text-[12px] text-muted">auth/verify.py</span>
          </div>
          <span className="rounded bg-surface-3 px-2 py-0.5 font-mono text-[10px] text-subtle">illustrative preview</span>
        </div>
        <div className="grid md:grid-cols-[1.4fr_1fr]">
          <div className="border-b border-border bg-bg/70 py-3 font-mono text-[12.5px] leading-[1.9] md:border-b-0 md:border-r">
            {[
              ["18", "import hmac, sqlite3", ""],
              ["19", 'SECRET = "sk-live-9f8e7d6c5b4a3f2e1d0c"', "crit"],
              ["20", "", ""],
              ["21", "def verify(user_id, token):", ""],
              ["22", '    cur.execute(f"SELECT * FROM users WHERE id={user_id}")', "high"],
              ["23", "    return token == SECRET", "med"],
            ].map(([n, code, sev]) => (
              <div key={n}>
                <div className={cn("flex gap-4 px-4", sev === "crit" && "bg-red-500/10", sev === "high" && "bg-orange-500/10", sev === "med" && "bg-amber-500/[0.07]")}>
                  <span className="w-6 shrink-0 text-right text-subtle">{n}</span><span className="whitespace-pre text-text/90">{code}</span>
                </div>
                {sev === "crit" && (
                  <div className="mx-4 my-1 rounded-md border border-border border-l-[3px] border-l-red-500 bg-surface-3 px-3 py-1.5 font-sans">
                    <p className="text-[10.5px] font-semibold uppercase tracking-wider text-red-400">Critical: hardcoded API token</p>
                    <p className="text-[12px] text-muted">Load the secret from an environment variable and rotate it.</p>
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="space-y-3 bg-surface/60 p-5">
            <p className="eyebrow">Review summary</p>
            <div className="flex items-center justify-between">
              <div><p className="font-display text-2xl font-semibold">Code Health: 41/100</p><p className="text-[13px] text-rose-400">At risk: fix critical issues first</p></div>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {[["1", "Critical", "bg-red-500/10 text-red-400"], ["1", "High", "bg-orange-500/10 text-orange-400"], ["2", "Medium", "bg-amber-500/10 text-amber-400"]].map(([n, l, c]) => (
                <div key={l} className={cn("rounded-lg py-2 text-center", c)}><p className="font-display text-lg font-semibold">{n}</p><p className="font-mono text-[9px] uppercase tracking-wider">{l}</p></div>
              ))}
            </div>
            <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/[0.06] p-3">
              <p className="font-mono text-[10px] font-semibold uppercase tracking-wider text-emerald-400">Recommended fix</p>
              <p className="mt-1 text-[12.5px]">Use a parameterized query: <code className="font-mono text-[11.5px] text-accent-text">cur.execute("… WHERE id = ?", (user_id,))</code></p>
            </div>
            <p className="flex items-center gap-1.5 font-mono text-[10.5px] text-subtle"><Cpu className="h-3.5 w-3.5" /> python-ast · ruff · bandit · radon</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Landing() {
  const { user } = useAuth();
  const [open, setOpen] = useState<number | null>(0);
  const cta = user ? { to: "/dashboard", label: "Open your workspace" } : { to: "/register", label: "Start reviewing code" };

  return (
    <div className="relative min-h-full overflow-x-hidden bg-bg">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[900px] bg-grid [mask-image:linear-gradient(to_bottom,black,transparent)]" />

      <header className="sticky top-0 z-40 border-b border-border/60 bg-bg/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-[1200px] items-center justify-between px-5 sm:px-8">
          <Link to="/home"><Logo version={false} /></Link>
          <nav className="hidden items-center gap-7 text-[13.5px] text-muted md:flex">
            <a href="#features" className="hover:text-text">Features</a>
            <a href="#how" className="hover:text-text">How it works</a>
            <a href="#languages" className="hover:text-text">Languages</a>
            <a href="#faq" className="hover:text-text">FAQ</a>
          </nav>
          <div className="flex items-center gap-2">
            {!user && <Link to="/login" className="px-3 text-[13.5px] text-muted hover:text-text">Sign in</Link>}
            <Link to={cta.to}><Button size="sm">{user ? "Dashboard" : "Get started"}</Button></Link>
          </div>
        </div>
      </header>

      <section className="relative mx-auto max-w-[1200px] px-5 pb-16 pt-16 text-center sm:px-8 sm:pt-24">
        <div className="flex justify-center"><StatusChip tone="accent" pulse>Static analysis + optional AI · 7 languages</StatusChip></div>
        <h1 className="mx-auto mt-6 max-w-4xl font-display text-[44px] font-semibold leading-[1.05] tracking-[-0.035em] sm:text-[64px]">
          Ship better code. <span className="bg-gradient-to-r from-violet-400 to-sky-400 bg-clip-text text-transparent">Faster.</span>
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-[17px] leading-relaxed text-muted">
          DevPilot AI reviews, debugs, explains, optimizes and documents your code in one workspace. It finds bugs, vulnerabilities and slow paths, then shows you exactly how to fix them.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link to={cta.to}><Button size="lg" className="glow-accent h-12 px-6 text-[15px]">{cta.label} <ArrowRight className="h-4 w-4" /></Button></Link>
          <a href="#how"><Button size="lg" variant="outline" className="h-12 px-6 text-[15px]">See how it works</Button></a>
        </div>
        <p className="mt-5 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 font-mono text-[11.5px] text-subtle">
          <span className="flex items-center gap-1.5"><Check className="h-3.5 w-3.5 text-emerald-400" /> Works without an AI key</span>
          <span className="flex items-center gap-1.5"><Check className="h-3.5 w-3.5 text-emerald-400" /> Code is never executed</span>
          <span className="flex items-center gap-1.5"><Check className="h-3.5 w-3.5 text-emerald-400" /> Export reports as Markdown or JSON</span>
        </p>
        <ProductPreview />
      </section>

      <section className="border-y border-border bg-rail/60">
        <div className="mx-auto grid max-w-[1200px] grid-cols-2 divide-border px-5 sm:px-8 md:grid-cols-4 md:divide-x">
          {[["7", "Languages supported"], ["4", "Analysis categories"], ["~45", "Known error patterns"], ["0", "Lines of your code executed"]].map(([v, l]) => (
            <div key={l} className="px-4 py-8 text-center">
              <p className="font-display text-[34px] font-semibold tracking-[-0.02em]">{v}</p>
              <p className="mt-1 font-mono text-[10.5px] uppercase tracking-wider text-subtle">{l}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="features" className="mx-auto max-w-[1200px] scroll-mt-20 px-5 py-20 sm:px-8">
        <p className="eyebrow text-center text-accent-text">Platform</p>
        <h2 className="mx-auto mt-3 max-w-2xl text-center font-display text-[34px] font-semibold leading-tight tracking-[-0.025em]">Built for code you can't afford to get wrong.</h2>
        <div className="mt-12 grid gap-4 md:grid-cols-2">
          {FEATURES.map(({ icon: Icon, title, tag, desc }) => (
            <div key={title} className="card group p-6 transition-colors hover:border-accent/40">
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-accent/25 bg-accent-soft text-accent-text"><Icon className="h-5 w-5" /></div>
                <span className="font-mono text-[10px] uppercase tracking-wider text-subtle">{tag}</span>
              </div>
              <h3 className="mt-5 font-display text-[19px] font-semibold">{title}</h3>
              <p className="mt-2 text-[14px] leading-relaxed text-muted">{desc}</p>
            </div>
          ))}
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {[
            [ShieldCheck, "Security analysis", "Hardcoded secrets, SQL injection, unsafe deserialization, dangerous functions and weak crypto."],
            [MessageSquareCode, "Inline findings", "Findings appear right in the editor under the line that caused them, with markers in the gutter."],
            [FileText, "Review history", "Search, filter by language or severity, reopen full reports and export them."],
          ].map(([Icon, t, d]) => {
            const I = Icon as typeof Lock;
            return (
              <div key={t as string} className="card p-5">
                <I className="h-5 w-5 text-sky-400" />
                <p className="mt-3 text-[15px] font-semibold">{t as string}</p>
                <p className="mt-1 text-[13px] leading-relaxed text-muted">{d as string}</p>
              </div>
            );
          })}
        </div>
      </section>

      <section id="how" className="scroll-mt-20 border-y border-border bg-rail/40">
        <div className="mx-auto max-w-[1200px] px-5 py-20 sm:px-8">
          <p className="eyebrow text-center text-accent-text">How it works</p>
          <h2 className="mt-3 text-center font-display text-[34px] font-semibold tracking-[-0.025em]">From paste to fix in under a minute.</h2>
          <div className="mt-12 grid gap-4 md:grid-cols-3">
            {STEPS.map(({ icon: Icon, title, desc }, i) => (
              <div key={title} className="card relative p-6">
                <span className="absolute right-5 top-5 font-display text-[42px] font-semibold leading-none text-surface-3">{String(i + 1).padStart(2, "0")}</span>
                <Icon className="h-6 w-6 text-accent-text" />
                <p className="mt-5 font-display text-[18px] font-semibold">{title}</p>
                <p className="mt-2 text-[14px] leading-relaxed text-muted">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="languages" className="mx-auto max-w-[1200px] scroll-mt-20 px-5 py-20 sm:px-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="eyebrow text-accent-text">Language engines</p>
            <h2 className="mt-3 font-display text-[30px] font-semibold tracking-[-0.025em]">Every language you ship.</h2>
          </div>
          <p className="max-w-md text-[14px] text-muted">Python gets the deepest analysis (AST, Ruff, Bandit, Radon). The other languages use DevPilot's rule engines, plus syntax checking where the toolchain is installed.</p>
        </div>
        <div className="mt-10 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          {LANGUAGES.map((l) => (
            <div key={l.value} className="card flex items-center gap-2.5 px-4 py-3.5">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: LANG_COLORS[l.value] }} />
              <span className="text-[14px] font-medium">{l.label}</span>
            </div>
          ))}
        </div>
      </section>

      <section id="faq" className="scroll-mt-20 border-t border-border">
        <div className="mx-auto max-w-3xl px-5 py-20 sm:px-8">
          <p className="eyebrow text-center text-accent-text">FAQ</p>
          <h2 className="mt-3 text-center font-display text-[30px] font-semibold tracking-[-0.025em]">Frequently asked questions</h2>
          <div className="mt-10 space-y-2.5">
            {FAQ.map(([q, a], i) => (
              <div key={q} className="card overflow-hidden">
                <button onClick={() => setOpen(open === i ? null : i)} className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left" aria-expanded={open === i}>
                  <span className="text-[15px] font-medium">{q}</span>
                  <ChevronDown className={cn("h-4 w-4 shrink-0 text-subtle transition-transform", open === i && "rotate-180")} />
                </button>
                {open === i && <p className="px-5 pb-5 text-[14px] leading-relaxed text-muted animate-fade-in">{a}</p>}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-[1200px] px-5 pb-20 sm:px-8">
        <div className="hero-gradient relative overflow-hidden rounded-2xl border border-border px-6 py-14 text-center shadow-card">
          <div className="pointer-events-none absolute inset-0 bg-grid opacity-60" />
          <div className="relative">
            <Sparkles className="mx-auto h-8 w-8 text-accent-text" />
            <h2 className="mx-auto mt-4 max-w-xl font-display text-[34px] font-semibold leading-tight tracking-[-0.025em]">Raise the quality bar on every commit.</h2>
            <p className="mx-auto mt-3 max-w-lg text-[15px] text-muted">Create a free workspace and run your first review in seconds.</p>
            <Link to={cta.to}><Button size="lg" className="glow-accent mt-7 h-12 px-6 text-[15px]">{cta.label} <ArrowRight className="h-4 w-4" /></Button></Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-4 px-5 py-8 sm:px-8">
          <Logo version={false} />
          <p className="font-mono text-[11px] text-subtle">© {new Date().getFullYear()} DevPilot AI · Intelligent code review & debugging</p>
        </div>
      </footer>
    </div>
  );
}
