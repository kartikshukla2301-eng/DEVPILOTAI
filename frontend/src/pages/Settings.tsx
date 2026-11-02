import { useEffect, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Cpu, FolderKanban, KeyRound, LogOut, Monitor, Moon, Pencil, Plus, Settings as SettingsIcon, SlidersHorizontal, Sparkles, Sun, Trash2, User as UserIcon } from "lucide-react";
import { ProjectModal } from "../components/ProjectModal";
import { Alert, Badge, Button, Card, ConfirmDialog, EmptyState, Field, Modal, PageHeader, Select, StatusChip, Toggle } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useNotify } from "../context/NotificationContext";
import { api, errorMessage } from "../lib/api";
import { LANGUAGES, langLabel } from "../lib/constants";
import type { Language, Level, Project, Theme, TokenResponse, User } from "../lib/types";
import { cn, formatDate } from "../lib/utils";
import { validatePassword } from "./AuthPages";

function ProfileSection() {
  const { user, setUser } = useAuth();
  const { notify } = useNotify();
  const [name, setName] = useState(user?.name ?? "");
  const [bio, setBio] = useState(user?.bio ?? "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const dirty = name.trim() !== user?.name || bio !== (user?.bio ?? "");

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return setErr("Name cannot be empty");
    setBusy(true);
    setErr(null);
    try {
      const r = await api.patch<User>("/users/me", { name: name.trim(), bio });
      setUser(r.data);
      notify("success", "Profile updated", { persist: false });
    } catch (e2) {
      setErr(errorMessage(e2));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title={<span className="flex items-center gap-2"><UserIcon className="h-4 w-4 text-accent" /> Profile</span>} subtitle={`Member since ${user ? formatDate(user.created_at, false) : ""}`}>
      <form onSubmit={save} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Full name" error={err ?? undefined}><input className="input" value={name} maxLength={100} onChange={(e) => setName(e.target.value)} /></Field>
          <Field label="Email" hint="Email cannot be changed."><input className="input" value={user?.email ?? ""} disabled /></Field>
        </div>
        <Field label="Bio"><textarea className="input min-h-20 resize-y" value={bio} maxLength={500} onChange={(e) => setBio(e.target.value)} placeholder="A short note about you (optional)" /></Field>
        <div className="flex justify-end"><Button type="submit" loading={busy} disabled={!dirty}>Save profile</Button></div>
      </form>
    </Card>
  );
}

function PasswordSection() {
  const { acceptToken } = useAuth();
  const { notify } = useNotify();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!current) errs.current = "Enter your current password";
    const v = validatePassword(next);
    if (v) errs.next = v;
    if (next && next === current) errs.next = "New password must be different";
    if (confirm !== next) errs.confirm = "Passwords do not match";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    try {
      const r = await api.post<TokenResponse>("/users/me/password", { current_password: current, new_password: next });
      acceptToken(r.data);
      setCurrent(""); setNext(""); setConfirm("");
      notify("success", "Password changed", { message: "Other sessions were signed out." });
    } catch (e2) {
      setErrors({ current: errorMessage(e2) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title={<span className="flex items-center gap-2"><KeyRound className="h-4 w-4 text-accent" /> Change password</span>} subtitle="Changing your password signs out all other devices.">
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-3" noValidate>
        <Field label="Current password" error={errors.current}><input type="password" className="input" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" /></Field>
        <Field label="New password" error={errors.next}><input type="password" className="input" value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" /></Field>
        <Field label="Confirm new password" error={errors.confirm}><input type="password" className="input" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" /></Field>
        <div className="flex justify-end sm:col-span-3"><Button type="submit" loading={busy}>Update password</Button></div>
      </form>
    </Card>
  );
}

function PreferencesSection() {
  const { settings, updateSettings, aiStatus } = useAuth();
  const { notify } = useNotify();
  const [saving, setSaving] = useState<string | null>(null);

  const update = async (key: string, patch: Parameters<typeof updateSettings>[0]) => {
    setSaving(key);
    try {
      await updateSettings(patch);
      notify("success", "Preferences saved", { persist: false });
    } catch (e) {
      notify("error", "Could not save preferences", { message: errorMessage(e) });
    } finally {
      setSaving(null);
    }
  };

  const themes: { value: Theme; label: string; icon: typeof Sun }[] = [
    { value: "dark", label: "Dark", icon: Moon }, { value: "light", label: "Light", icon: Sun }, { value: "system", label: "System", icon: Monitor },
  ];

  return (
    <Card title={<span className="flex items-center gap-2"><SlidersHorizontal className="h-4 w-4 text-accent" /> Preferences</span>} subtitle="Saved to your account and applied on every device.">
      <div className="space-y-5">
        <div>
          <p className="label">Theme</p>
          <div className="grid max-w-md grid-cols-3 gap-2">
            {themes.map(({ value, label, icon: Icon }) => (
              <button key={value} onClick={() => update("theme", { theme: value })} disabled={saving === "theme"}
                className={cn("flex flex-col items-center gap-1.5 rounded-lg border px-3 py-3 text-[13px] transition-colors", settings.theme === value ? "border-accent bg-accent-soft" : "border-border hover:bg-surface-2")}>
                <Icon className={cn("h-4 w-4", settings.theme === value ? "text-accent" : "text-muted")} />{label}
              </button>
            ))}
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Default programming language" hint="Pre-selected in the editors.">
            <Select value={settings.default_language} onChange={(e) => update("lang", { default_language: e.target.value as Language })}>
              {LANGUAGES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
            </Select>
          </Field>
          <Field label="Default explanation level">
            <Select value={settings.explanation_level} onChange={(e) => update("level", { explanation_level: e.target.value as Level })}>
              <option value="beginner">Beginner</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option>
            </Select>
          </Field>
        </div>
        <Toggle checked={settings.use_ai} disabled={!aiStatus?.ai_configured || saving === "ai"} onChange={(v) => update("ai", { use_ai: v })}
          label="Use AI when available" description={aiStatus?.ai_configured ? "Turn off to always use local rule-based analysis." : "AI is not configured on the server, so local analysis is always used."} />
      </div>
    </Card>
  );
}

function AISection() {
  const { aiStatus, aiActive } = useAuth();
  return (
    <section id="ai" className="scroll-mt-24">
      <Card title={<span className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-accent" /> AI configuration</span>}>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg border border-border bg-surface-2 px-4 py-3">
            <p className="text-xs text-muted">Status</p>
            <p className="mt-1 flex items-center gap-2 text-sm font-medium">
              {aiStatus?.ai_configured ? <><span className="h-2 w-2 rounded-full bg-emerald-400" /> Configured</> : <><span className="h-2 w-2 rounded-full bg-subtle" /> Not configured</>}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-surface-2 px-4 py-3">
            <p className="text-xs text-muted">Active mode</p>
            <p className="mt-1 text-sm font-medium">{aiActive ? <Badge tone="accent"><Sparkles className="h-3 w-3" /> AI-assisted</Badge> : <Badge tone="blue"><Cpu className="h-3 w-3" /> Local analysis</Badge>}</p>
          </div>
          <div className="rounded-lg border border-border bg-surface-2 px-4 py-3">
            <p className="text-xs text-muted">Model / provider</p>
            <p className="mt-1 truncate text-sm font-medium">{aiStatus?.model ? `${aiStatus.model} · ${aiStatus.provider_host}` : "—"}</p>
          </div>
        </div>
        <div className="mt-4">
          {aiStatus?.ai_configured ? (
            <Alert tone="info">AI findings are always labelled separately from static analysis. The API key stays on the server and is never sent to the browser.</Alert>
          ) : (
            <Alert tone="info" title="Running in local analysis mode">
              All modules work using Ruff, Bandit, Radon, Python AST and DevPilot's language rules. To enable AI, set <code className="rounded bg-surface-3 px-1 font-mono">AI_API_KEY</code> (and optionally <code className="rounded bg-surface-3 px-1 font-mono">AI_BASE_URL</code>, <code className="rounded bg-surface-3 px-1 font-mono">AI_MODEL</code>) in <code className="rounded bg-surface-3 px-1 font-mono">backend/.env</code> for any OpenAI-compatible provider and restart the backend.
            </Alert>
          )}
        </div>
      </Card>
    </section>
  );
}

function ProjectsSection() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [edit, setEdit] = useState<Project | null>(null);
  const [open, setOpen] = useState(false);
  const [toDelete, setToDelete] = useState<Project | null>(null);
  const [deleting, setDeleting] = useState(false);
  const { notify } = useNotify();
  const load = () => api.get<Project[]>("/projects").then((r) => setProjects(r.data)).catch(() => setProjects([]));
  useEffect(() => { load(); }, []);

  const remove = async () => {
    if (!toDelete) return;
    setDeleting(true);
    try {
      await api.delete(`/projects/${toDelete.id}`);
      notify("success", "Project deleted", { message: "Its reviews were kept and are now unassigned.", persist: false });
      setToDelete(null);
      load();
    } catch (e) {
      notify("error", "Could not delete project", { message: errorMessage(e) });
    } finally {
      setDeleting(false);
    }
  };

  return (
    <section id="projects" className="scroll-mt-24">
    <Card padded={false} title={<span className="flex items-center gap-2"><FolderKanban className="h-4 w-4 text-accent-text" /> Projects</span>}
      action={<Button size="sm" variant="outline" icon={<Plus className="h-3.5 w-3.5" />} onClick={() => { setEdit(null); setOpen(true); }}>New project</Button>}>
      {projects && projects.length === 0 ? (
        <EmptyState icon={<FolderKanban className="h-5 w-5" />} title="No projects yet" description="Projects group related code reviews." />
      ) : (
        <ul>
          {(projects ?? []).map((p) => (
            <li key={p.id} className="flex items-center gap-3 border-b border-border px-5 py-3 last:border-0">
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-medium">{p.name}</p>
                <p className="truncate text-xs text-muted">{p.review_count} review{p.review_count === 1 ? "" : "s"}{p.language ? ` · ${langLabel(p.language)}` : ""}{p.description ? ` · ${p.description}` : ""}</p>
              </div>
              <Button size="icon" variant="ghost" aria-label="Edit project" onClick={() => { setEdit(p); setOpen(true); }}><Pencil className="h-4 w-4" /></Button>
              <Button size="icon" variant="ghost" aria-label="Delete project" className="hover:text-red-400" onClick={() => setToDelete(p)}><Trash2 className="h-4 w-4" /></Button>
            </li>
          ))}
        </ul>
      )}
      <ProjectModal open={open} project={edit} onClose={() => setOpen(false)} onSaved={load} />
      <ConfirmDialog open={!!toDelete} onClose={() => setToDelete(null)} onConfirm={remove} loading={deleting} title="Delete project?"
        message={<>“{toDelete?.name}” will be deleted. Its reviews stay in your history without a project.</>} />
    </Card>
    </section>
  );
}

function AccountSection() {
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const { notify } = useNotify();

  const deleteAccount = async () => {
    setBusy(true);
    try {
      await api.delete("/users/me");
      await logout({ silent: true });
      navigate("/register");
    } catch (e) {
      notify("error", "Could not delete account", { message: errorMessage(e) });
      setBusy(false);
    }
  };

  return (
    <Card title="Account">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
        <div><p className="text-[13px] font-medium">Log out</p><p className="text-xs text-muted">Signs you out on all devices by revoking every active session token.</p></div>
        <Button variant="outline" icon={<LogOut className="h-4 w-4" />} onClick={async () => { await logout(); navigate("/login"); }}>Log out</Button>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 pt-4">
        <div><p className="text-[13px] font-medium text-red-400">Delete account</p><p className="text-xs text-muted">Permanently removes your account, projects and all saved analyses.</p></div>
        <Button variant="danger" icon={<Trash2 className="h-4 w-4" />} onClick={() => { setTyped(""); setOpen(true); }}>Delete account</Button>
      </div>
      <Modal open={open} onClose={() => setOpen(false)} title="Delete your account?"
        footer={<><Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button><Button variant="danger" loading={busy} disabled={typed !== user?.email} onClick={deleteAccount}>Delete permanently</Button></>}>
        <p className="text-[13px] text-muted">This deletes all your data and cannot be undone. Type <span className="font-mono text-text">{user?.email}</span> to confirm.</p>
        <input className="input mt-3" value={typed} onChange={(e) => setTyped(e.target.value)} aria-label="Confirm email" />
      </Modal>
    </Card>
  );
}

export default function SettingsPage() {
  const location = useLocation();
  useEffect(() => {
    if (location.hash) setTimeout(() => document.querySelector(location.hash)?.scrollIntoView({ behavior: "smooth" }), 100);
  }, [location.hash]);
  return (
    <>
      <PageHeader eyebrow={<StatusChip tone="neutral"><SettingsIcon className="h-3 w-3" /> Preferences</StatusChip>} meta="account · workspace" title="Settings"
        description="Manage your profile, security, preferences, projects and AI configuration." />
      <div className="grid gap-4 xl:grid-cols-2">
        <div className="space-y-4">
          <ProfileSection />
          <PasswordSection />
          <ProjectsSection />
        </div>
        <div className="space-y-4">
          <PreferencesSection />
          <AISection />
          <AccountSection />
        </div>
      </div>
    </>
  );
}
