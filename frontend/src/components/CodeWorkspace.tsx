import { forwardRef, useRef, useState, type ReactNode } from "react";
import { Eraser, Pencil, Upload, Wand2 } from "lucide-react";
import { useNotify } from "../context/NotificationContext";
import { EXT_TO_LANG, LANGUAGES, langExt, langLabel } from "../lib/constants";
import type { Finding, Language } from "../lib/types";
import { cn, readFileAsText } from "../lib/utils";
import { CodeEditor, EditorFrame, type CodeEditorHandle } from "./CodeEditor";

const MAX_FILE_BYTES = 800_000;

interface Props {
  code: string;
  setCode: (v: string) => void;
  language: Language;
  setLanguage: (l: Language) => void;
  filename?: string;
  setFilename?: (f: string) => void;
  sample?: (l: Language) => string;
  height?: number | string;
  findings?: Finding[];
  inlineFindings?: boolean;
  onFindingClick?: (f: Finding) => void;
  highlightLine?: number | null;
  /** Extra controls rendered in a toolbar row under the tab bar. */
  toolbar?: ReactNode;
  readOnly?: boolean;
}

function IconBtn({ onClick, label, children }: { onClick: () => void; label: string; children: ReactNode }) {
  return (
    <button onClick={onClick} title={label} aria-label={label}
      className="flex h-7 items-center gap-1.5 rounded-md px-2 text-[12px] text-muted transition-colors hover:bg-surface-3 hover:text-text">
      {children}<span className="hidden md:inline">{label}</span>
    </button>
  );
}

export const CodeWorkspace = forwardRef<CodeEditorHandle, Props>(function CodeWorkspace(
  { code, setCode, language, setLanguage, filename, setFilename, sample, height = 460, findings, inlineFindings, onFindingClick, highlightLine, toolbar, readOnly }, ref,
) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [editingName, setEditingName] = useState(false);
  const [dragging, setDragging] = useState(false);
  const { notify } = useNotify();
  const shownName = filename?.trim() || `untitled.${langExt(language)}`;

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
    const lang = EXT_TO_LANG[ext];
    if (!lang) {
      notify("error", "Unsupported file type", { message: `.${ext} files are not supported. Use ${Object.keys(EXT_TO_LANG).map((e) => "." + e).join(", ")}.` });
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      notify("error", "File is too large", { message: "Maximum size is 800 KB." });
      return;
    }
    try {
      const text = await readFileAsText(file);
      setCode(text);
      setLanguage(lang);
      setFilename?.(file.name);
      notify("info", `Loaded ${file.name}`, { persist: false });
    } catch {
      notify("error", "Could not read the file");
    }
  };

  const nameControl = setFilename && editingName ? (
    <input autoFocus className="w-40 bg-transparent font-mono text-[12px] outline-none" defaultValue={filename} maxLength={120} placeholder={shownName}
      onBlur={(e) => { setFilename(e.target.value.trim()); setEditingName(false); }}
      onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); if (e.key === "Escape") setEditingName(false); }} aria-label="File name" />
  ) : null;

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); if (!readOnly) setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => { e.preventDefault(); setDragging(false); if (!readOnly) onFile(e.dataTransfer.files?.[0]); }}
      className={cn("relative rounded-xl transition-shadow", dragging && "ring-2 ring-accent")}
    >
      <EditorFrame
        filename={nameControl ?? shownName}
        language={langLabel(language)}
        right={!readOnly && (
          <>
            {setFilename && !editingName && <IconBtn onClick={() => setEditingName(true)} label="Rename"><Pencil className="h-3.5 w-3.5" /></IconBtn>}
            <input ref={fileInput} type="file" className="hidden" accept={Object.keys(EXT_TO_LANG).map((e) => "." + e).join(",")}
              onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = ""; }} />
            <IconBtn onClick={() => fileInput.current?.click()} label="Upload"><Upload className="h-3.5 w-3.5" /></IconBtn>
            {sample && <IconBtn onClick={() => { setCode(sample(language)); setFilename?.(""); }} label="Load sample"><Wand2 className="h-3.5 w-3.5" /></IconBtn>}
            {code && <IconBtn onClick={() => setCode("")} label="Clear"><Eraser className="h-3.5 w-3.5" /></IconBtn>}
          </>
        )}
        footer={<>
          <span className="flex items-center gap-3">
            <select value={language} onChange={(e) => setLanguage(e.target.value as Language)} disabled={readOnly} aria-label="Language"
              className="cursor-pointer rounded bg-transparent font-mono text-[10.5px] text-muted outline-none hover:text-text">
              {LANGUAGES.map((l) => <option key={l.value} value={l.value} className="bg-surface">{l.label}</option>)}
            </select>
            <span>UTF-8</span>
            <span>{code.split("\n").length.toLocaleString()} lines · {code.length.toLocaleString()} chars</span>
          </span>
          <span className="flex items-center gap-1.5 text-emerald-400/90"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Parse-only · code is never executed</span>
        </>}
      >
        {toolbar && <div className="flex flex-wrap items-center gap-2 border-b border-border bg-surface px-3 py-2">{toolbar}</div>}
        <div className="relative">
          <CodeEditor ref={ref} bare value={code} onChange={setCode} language={language} height={height} findings={findings}
            inlineFindings={inlineFindings} onFindingClick={onFindingClick} highlightLine={highlightLine} readOnly={readOnly} />
          {!code && !readOnly && (
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-2 text-center">
              <p className="text-sm text-muted">Paste or type code here</p>
              <p className="font-mono text-[11px] text-subtle">or drop a source file · upload · load a sample</p>
            </div>
          )}
        </div>
      </EditorFrame>
    </div>
  );
});
