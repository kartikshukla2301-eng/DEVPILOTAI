import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { AlertCircle, ArrowLeft, ArrowRight, AtSign, Check, Cpu, Eye, EyeOff, KeyRound, Lock, ShieldCheck, Sparkles, User as UserIcon } from "lucide-react";
import { Logo } from "../components/layout/AppLayout";
import { Button, Checkbox } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { api, errorMessage } from "../lib/api";
import { cn } from "../lib/utils";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function useApiStatus() {
  const [s, setS] = useState<{ ok: boolean | null; mode?: string }>({ ok: null });
  useEffect(() => {
    api.get<{ status: string; analysis_mode: string }>("/health", { timeout: 6000 })
      .then((r) => setS({ ok: r.data.status === "ok", mode: r.data.analysis_mode }))
      .catch(() => setS({ ok: false }));
  }, []);
  return s;
}

/** Illustrative terminal showing what a review produces. Clearly labelled as an example. */
function ExampleTerminal() {
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between border-b border-border bg-surface-2 px-4 py-2.5">
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5"><span className="h-3 w-3 rounded-full bg-[#ff5f57]" /><span className="h-3 w-3 rounded-full bg-[#38bdf8]" /><span className="h-3 w-3 rounded-full bg-[#28c840]" /></div>
          <span className="font-mono text-[12px] text-muted">review — payments.py</span>
        </div>
        <span className="rounded bg-surface-3 px-1.5 py-0.5 font-mono text-[10px] text-subtle">example output</span>
      </div>
      <div className="space-y-1.5 bg-bg px-4 py-3.5 font-mono text-[12px] leading-relaxed">
        <p><span className="text-emerald-400">➜</span> <span className="text-subtle">analyzers</span> python-ast · ruff · bandit · radon</p>
        <p><span className="rounded bg-red-500/15 px-1 text-red-400">CRITICAL</span> <span className="text-subtle">L5</span> API token in source</p>
        <p><span className="rounded bg-orange-500/15 px-1 text-orange-400">HIGH</span> <span className="text-subtle">L10</span> Possible SQL injection (f-string → execute)</p>
        <p><span className="rounded bg-amber-500/15 px-1 text-amber-400">MEDIUM</span> <span className="text-subtle">L14</span> String concatenation inside a loop</p>
        <p className="pt-1 text-accent-text"><Sparkles className="mr-1 inline h-3.5 w-3.5" />Code health 34/100 · suggested fix ready</p>
      </div>
    </div>
  );
}

function AuthShell({ title, subtitle, children, footer }: { title: string; subtitle: string; children: ReactNode; footer: ReactNode }) {
  const status = useApiStatus();
  return (
    <div className="relative min-h-full overflow-x-hidden bg-bg">
      <div className="pointer-events-none absolute inset-0 bg-grid" />
      <div className="pointer-events-none absolute -left-40 top-20 h-[420px] w-[420px] rounded-full bg-accent/10 blur-[110px]" />
      <div className="pointer-events-none absolute -right-32 bottom-0 h-[380px] w-[380px] rounded-full bg-sky-500/10 blur-[110px]" />

      <header className="relative mx-auto flex max-w-[1240px] items-center justify-between px-5 py-6 sm:px-8">
        <Link to="/home"><Logo version={false} /></Link>
        <Link to="/home" className="flex items-center gap-1.5 text-[13px] text-muted hover:text-text"><ArrowLeft className="h-4 w-4" /> Back to website</Link>
      </header>

      <main className="relative mx-auto grid max-w-[1240px] gap-6 px-5 pb-10 pt-4 sm:px-8 lg:grid-cols-[1.35fr_1fr] lg:pt-10">
        <section className="glass animate-fade-in rounded-2xl p-6 sm:p-10">
          <div className="mb-7 flex flex-wrap items-center justify-between gap-2 font-mono text-[11px]">
            <div className="flex items-center gap-2">
              <span className="rounded bg-surface-3 px-2 py-1 text-muted">V1.0</span>
              <span className={cn("flex items-center gap-1.5 rounded px-2 py-1",
                status.ok == null ? "bg-surface-3 text-subtle" : status.ok ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400")}>
                <span className="h-1.5 w-1.5 rounded-full bg-current" />
                {status.ok == null ? "Checking API…" : status.ok ? "API online" : "API unreachable"}
              </span>
            </div>
            {status.mode && <span className="flex items-center gap-1.5 text-muted">{status.mode === "ai" ? <Sparkles className="h-3.5 w-3.5" /> : <Cpu className="h-3.5 w-3.5" />}{status.mode === "ai" ? "AI + static engine" : "Local analysis mode"}</span>}
          </div>
          <h1 className="font-display text-[30px] font-semibold leading-tight tracking-[-0.025em] sm:text-[38px]">{title}</h1>
          <p className="mt-2 text-[15px] text-muted">{subtitle}</p>
          <div className="mt-8">{children}</div>
          <p className="mt-7 text-center text-[13px] text-muted">{footer}</p>
        </section>

        <aside className="hidden flex-col gap-6 lg:flex">
          <ExampleTerminal />
          <div className="card p-5">
            <p className="eyebrow mb-3">What runs on your code</p>
            <ul className="space-y-2.5 text-[13px]">
              {[
                ["Bug, quality, security & performance review", "7 languages · line-level findings"],
                ["Debugging assistant", "Root cause, steps and a patch"],
                ["Explainer, optimizer & doc generator", "Beginner to advanced explanations"],
              ].map(([t, d]) => (
                <li key={t} className="flex gap-2.5"><Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" /><span><span className="font-medium">{t}</span><span className="block text-xs text-muted">{d}</span></span></li>
              ))}
            </ul>
          </div>
          <div className="card p-5">
            <p className="eyebrow mb-3">Security by design</p>
            <div className="grid grid-cols-2 gap-2">
              {[
                [ShieldCheck, "bcrypt password hashing"], [KeyRound, "Revocable JWT sessions"],
                [Lock, "Code parsed, never executed"], [UserIcon, "Per-user data isolation"],
              ].map(([Icon, t]) => {
                const I = Icon as typeof Lock;
                return <div key={t as string} className="flex items-center gap-2 rounded-lg border border-border bg-surface-2 px-3 py-2.5 text-[12.5px]"><I className="h-4 w-4 shrink-0 text-emerald-400" />{t as string}</div>;
              })}
            </div>
          </div>
        </aside>
      </main>

      <footer className="relative mx-auto flex max-w-[1240px] flex-wrap items-center justify-between gap-3 px-5 pb-8 font-mono text-[11px] text-subtle sm:px-8">
        <span>Python · JavaScript · TypeScript · Java · C++ · C · Go</span>
        <span>© {new Date().getFullYear()} DevPilot AI</span>
      </footer>
    </div>
  );
}

function InputWithIcon({ icon, invalid, right, ...rest }: React.InputHTMLAttributes<HTMLInputElement> & { icon: ReactNode; invalid?: boolean; right?: ReactNode }) {
  return (
    <div className="relative">
      <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-subtle">{icon}</span>
      <input {...rest} aria-invalid={invalid} className={cn("input h-12 bg-bg pl-11 text-[14px]", right ? "pr-11" : "", invalid && "border-red-500/60")} />
      {right && <span className="absolute right-2 top-1/2 -translate-y-1/2">{right}</span>}
    </div>
  );
}

function PasswordInput({ value, onChange, id, autoComplete, invalid, placeholder }: { value: string; onChange: (v: string) => void; id: string; autoComplete: string; invalid?: boolean; placeholder?: string }) {
  const [show, setShow] = useState(false);
  return (
    <InputWithIcon id={id} icon={<Lock className="h-4 w-4" />} type={show ? "text" : "password"} value={value} onChange={(e) => onChange(e.target.value)}
      autoComplete={autoComplete} invalid={invalid} maxLength={128} placeholder={placeholder ?? "••••••••••"}
      right={<button type="button" onClick={() => setShow((s) => !s)} className="rounded p-1.5 text-subtle hover:text-text" aria-label={show ? "Hide password" : "Show password"}>
        {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>} />
  );
}

function FieldLabel({ htmlFor, children, error }: { htmlFor: string; children: ReactNode; error?: string }) {
  return (
    <div className="mb-2 flex items-center justify-between">
      <label htmlFor={htmlFor} className="text-[13px] font-medium">{children}</label>
      {error && <span className="text-xs text-red-400">{error}</span>}
    </div>
  );
}

function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2.5 text-[13px] text-red-400" role="alert">
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{message}
    </div>
  );
}

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!EMAIL_RE.test(email.trim())) errs.email = "Enter a valid email address";
    if (!password) errs.password = "Enter your password";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password, remember);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from && from !== "/login" ? from : "/dashboard", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Welcome back to DevPilot" subtitle="Sign in to your code intelligence workspace."
      footer={<>Don't have a workspace yet? <Link className="font-medium text-accent-text hover:underline" to="/register">Create one now</Link></>}>
      <form onSubmit={submit} noValidate className="space-y-5">
        <FormError message={error} />
        <div>
          <FieldLabel htmlFor="email" error={errors.email}>Email</FieldLabel>
          <InputWithIcon id="email" icon={<AtSign className="h-4 w-4" />} type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" autoFocus invalid={!!errors.email} placeholder="you@company.com" />
        </div>
        <div>
          <FieldLabel htmlFor="password" error={errors.password}>Password</FieldLabel>
          <PasswordInput id="password" value={password} onChange={setPassword} autoComplete="current-password" invalid={!!errors.password} />
        </div>
        <Checkbox checked={remember} onChange={setRemember} label="Remember this device" />
        <Button type="submit" size="lg" className="glow-accent h-12 w-full text-[15px]" loading={busy} kbd="↵ Enter">
          Sign in to workspace <ArrowRight className="h-4 w-4" />
        </Button>
      </form>
    </AuthShell>
  );
}

function strength(pw: string): { score: number; label: string; color: string } {
  let s = 0;
  if (pw.length >= 8) s++;
  if (pw.length >= 12) s++;
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) s++;
  if (/\d/.test(pw)) s++;
  if (/[^A-Za-z0-9]/.test(pw)) s++;
  const labels = ["Too weak", "Weak", "Fair", "Good", "Strong", "Very strong"];
  const colors = ["#ef4444", "#ef4444", "#f97316", "#f59e0b", "#22c55e", "#22c55e"];
  return { score: s, label: labels[s], color: colors[s] };
}

export function validatePassword(pw: string): string | null {
  if (pw.length < 8) return "Use at least 8 characters";
  if (!/[A-Za-z]/.test(pw) || !/\d/.test(pw)) return "Include a letter and a number";
  return null;
}

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const st = strength(password);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!name.trim()) errs.name = "Enter your name";
    if (!EMAIL_RE.test(email.trim())) errs.email = "Enter a valid email address";
    const pwErr = validatePassword(password);
    if (pwErr) errs.password = pwErr;
    if (confirm !== password) errs.confirm = "Passwords do not match";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    setError(null);
    try {
      await register(name.trim(), email.trim(), password);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Create your workspace" subtitle="Start reviewing, debugging and documenting code in minutes. No credit card, no setup."
      footer={<>Already have an account? <Link className="font-medium text-accent-text hover:underline" to="/login">Sign in</Link></>}>
      <form onSubmit={submit} noValidate className="space-y-5">
        <FormError message={error} />
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <FieldLabel htmlFor="name" error={errors.name}>Full name</FieldLabel>
            <InputWithIcon id="name" icon={<UserIcon className="h-4 w-4" />} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" maxLength={100} autoFocus invalid={!!errors.name} placeholder="Ada Lovelace" />
          </div>
          <div>
            <FieldLabel htmlFor="email" error={errors.email}>Email</FieldLabel>
            <InputWithIcon id="email" icon={<AtSign className="h-4 w-4" />} type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" invalid={!!errors.email} placeholder="you@company.com" />
          </div>
        </div>
        <div>
          <FieldLabel htmlFor="password" error={errors.password}>Password</FieldLabel>
          <PasswordInput id="password" value={password} onChange={setPassword} autoComplete="new-password" invalid={!!errors.password} placeholder="At least 8 characters, a letter and a number" />
          {password && (
            <div className="mt-2 flex items-center gap-2">
              <div className="flex flex-1 gap-1">
                {[0, 1, 2, 3, 4].map((i) => <div key={i} className="h-1 flex-1 rounded-full transition-colors" style={{ background: i < st.score ? st.color : "var(--surface-3)" }} />)}
              </div>
              <span className="w-20 text-right font-mono text-[10.5px]" style={{ color: st.color }}>{st.label}</span>
            </div>
          )}
        </div>
        <div>
          <FieldLabel htmlFor="confirm" error={errors.confirm}>Confirm password</FieldLabel>
          <PasswordInput id="confirm" value={confirm} onChange={setConfirm} autoComplete="new-password" invalid={!!errors.confirm} />
        </div>
        <Button type="submit" size="lg" className="glow-accent h-12 w-full text-[15px]" loading={busy}>
          Create workspace <ArrowRight className="h-4 w-4" />
        </Button>
      </form>
    </AuthShell>
  );
}
