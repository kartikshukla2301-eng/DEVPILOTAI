import { useEffect, useState } from "react";
import { useNotify } from "../context/NotificationContext";
import { api, errorMessage } from "../lib/api";
import { LANGUAGES } from "../lib/constants";
import type { Language, Project } from "../lib/types";
import { Button, Field, Modal, Select } from "./ui";

export function ProjectModal({ open, onClose, onSaved, project }: { open: boolean; onClose: () => void; onSaved: (p: Project) => void; project?: Project | null }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [language, setLanguage] = useState<Language | "">("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { notify } = useNotify();

  useEffect(() => {
    if (open) {
      setName(project?.name ?? "");
      setDescription(project?.description ?? "");
      setLanguage(project?.language ?? "");
      setError(null);
    }
  }, [open, project]);

  const save = async () => {
    if (!name.trim()) {
      setError("Project name is required");
      return;
    }
    setBusy(true);
    try {
      const body = { name: name.trim(), description: description.trim(), language: language || null };
      const r = project ? await api.patch<Project>(`/projects/${project.id}`, body) : await api.post<Project>("/projects", body);
      notify("success", project ? "Project updated" : "Project created", { message: r.data.name, persist: false });
      onSaved(r.data);
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title={project ? "Edit project" : "New project"}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button loading={busy} onClick={save}>{project ? "Save changes" : "Create project"}</Button></>}>
      <div className="space-y-4">
        <Field label="Name" error={error ?? undefined}>
          <input className="input" value={name} maxLength={100} onChange={(e) => setName(e.target.value)} autoFocus placeholder="e.g. Payments service" />
        </Field>
        <Field label="Description">
          <textarea className="input min-h-20 resize-y" value={description} maxLength={1000} onChange={(e) => setDescription(e.target.value)} placeholder="What is this project about?" />
        </Field>
        <Field label="Primary language">
          <Select value={language} onChange={(e) => setLanguage(e.target.value as Language | "")}>
            <option value="">Mixed / not set</option>
            {LANGUAGES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
          </Select>
        </Field>
      </div>
    </Modal>
  );
}
