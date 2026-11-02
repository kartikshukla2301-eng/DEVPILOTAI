import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import Editor, { DiffEditor, type OnMount } from "@monaco-editor/react";
import { monaco } from "../lib/monaco";
import { SEVERITY_META, langMonaco } from "../lib/constants";
import type { Finding, Language } from "../lib/types";
import { useResolvedTheme } from "../lib/useTheme";
import { Spinner } from "./ui";

export interface CodeEditorHandle {
  revealLine: (line: number) => void;
  focus: () => void;
}

interface Props {
  value: string;
  onChange?: (v: string) => void;
  language: Language;
  height?: number | string;
  readOnly?: boolean;
  findings?: Finding[];
  /** Render the most important findings as banners inside the editor, below their line. */
  inlineFindings?: boolean;
  onFindingClick?: (f: Finding) => void;
  highlightLine?: number | null;
  path?: string;
  bare?: boolean;
}

const SEV_TO_MARKER: Record<string, monaco.MarkerSeverity> = {
  critical: monaco.MarkerSeverity.Error,
  high: monaco.MarkerSeverity.Error,
  medium: monaco.MarkerSeverity.Warning,
  low: monaco.MarkerSeverity.Info,
  info: monaco.MarkerSeverity.Hint,
};
const CATEGORY_LABEL: Record<string, string> = { bug: "Bug", security: "Vulnerability", quality: "Code quality", performance: "Optimization" };
const MAX_ZONES = 14;

const Loading = () => (
  <div className="flex h-full w-full items-center justify-center bg-surface"><Spinner /></div>
);

export const CodeEditor = forwardRef<CodeEditorHandle, Props>(function CodeEditor(
  { value, onChange, language, height = 420, readOnly, findings, inlineFindings, onFindingClick, highlightLine, path, bare }, ref,
) {
  const theme = useResolvedTheme();
  const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);
  const decoRef = useRef<monaco.editor.IEditorDecorationsCollection | null>(null);
  const zoneIds = useRef<string[]>([]);
  const zoneFindings = useRef(new Map<string, Finding>());
  const clickRef = useRef(onFindingClick);
  clickRef.current = onFindingClick;

  useImperativeHandle(ref, () => ({
    revealLine: (line: number) => {
      const ed = editorRef.current;
      if (!ed) return;
      ed.revealLineInCenter(line);
      ed.setPosition({ lineNumber: line, column: 1 });
      ed.focus();
    },
    focus: () => editorRef.current?.focus(),
  }));

  const apply = () => {
    const ed = editorRef.current;
    const model = ed?.getModel();
    if (!ed || !model) return;
    const lineCount = model.getLineCount();
    const valid = (findings ?? []).filter((f) => f.line && f.line <= lineCount);

    monaco.editor.setModelMarkers(model, "devpilot", valid.map((f) => {
      const end = f.end_line && f.end_line <= lineCount ? f.end_line : f.line!;
      return {
        startLineNumber: f.line!, endLineNumber: end, startColumn: 1, endColumn: model.getLineMaxColumn(end),
        message: `${f.title}\n${f.recommendation}`, severity: SEV_TO_MARKER[f.severity],
        source: f.source === "ai" ? "DevPilot AI" : `DevPilot · ${f.tool}`,
      };
    }));

    const decos: monaco.editor.IModelDeltaDecoration[] = valid.map((f) => ({
      range: new monaco.Range(f.line!, 1, f.line!, 1),
      options: {
        isWholeLine: Boolean(inlineFindings),
        className: inlineFindings ? `dp-line-${f.severity}` : undefined,
        glyphMarginClassName: `dp-glyph-${f.severity}`,
        glyphMarginHoverMessage: { value: `**${f.severity.toUpperCase()}** ${f.title}` },
      },
    }));
    if (highlightLine && highlightLine <= lineCount) {
      decos.push({ range: new monaco.Range(highlightLine, 1, highlightLine, 1), options: { isWholeLine: true, className: "dp-line-highlight" } });
    }
    decoRef.current?.set(decos);

    // Inline finding banners (view zones): one per line, worst finding wins.
    ed.changeViewZones((acc) => {
      zoneIds.current.forEach((id) => acc.removeZone(id));
      zoneIds.current = [];
      zoneFindings.current.clear();
      if (!inlineFindings) return;
      const perLine = new Map<number, Finding>();
      for (const f of valid) if (!perLine.has(f.line!)) perLine.set(f.line!, f); // findings arrive worst-first
      [...perLine.values()].slice(0, MAX_ZONES).forEach((f) => {
        const color = SEVERITY_META[f.severity].color;
        const node = document.createElement("div");
        node.className = "dp-zone";
        const card = document.createElement("div");
        card.className = "dp-zone-card";
        card.style.borderLeftColor = color;
        card.title = "Open this finding in the inspector";
        const body = document.createElement("div");
        body.style.minWidth = "0";
        const title = document.createElement("div");
        title.className = "dp-zone-title";
        title.style.color = color;
        title.textContent = `${f.severity}: ${CATEGORY_LABEL[f.category] ?? f.category}${f.rule ? ` ${f.rule}` : ""}${f.source === "ai" ? " · AI" : ""}`;
        const desc = document.createElement("div");
        desc.className = "dp-zone-desc";
        desc.textContent = f.title;
        body.append(title, desc);
        card.append(body);
        node.append(card);
        const id = acc.addZone({ afterLineNumber: f.line!, heightInPx: 62, domNode: node });
        zoneIds.current.push(id);
        zoneFindings.current.set(id, f);
      });
    });
  };

  const onMount: OnMount = (ed) => {
    editorRef.current = ed;
    decoRef.current = ed.createDecorationsCollection();
    // Monaco's text layer sits above view zones, so DOM listeners on the zone never fire.
    // Use the editor's own hit-testing to detect clicks on a finding banner.
    ed.onMouseDown((e) => {
      if (e.target.type !== monaco.editor.MouseTargetType.CONTENT_VIEW_ZONE) return;
      const f = zoneFindings.current.get((e.target.detail as { viewZoneId: string }).viewZoneId);
      if (f) clickRef.current?.(f);
    });
    apply();
  };

  useEffect(apply);

  return (
    <div className={bare ? "overflow-hidden" : "overflow-hidden rounded-lg border border-border"} style={{ height }}>
      <Editor
        height="100%"
        path={path}
        language={langMonaco(language)}
        value={value}
        theme={theme === "light" ? "devpilot-light" : "devpilot-dark"}
        onChange={(v) => onChange?.(v ?? "")}
        onMount={onMount}
        loading={<Loading />}
        options={{
          readOnly,
          minimap: { enabled: false },
          fontSize: 13,
          lineHeight: 20,
          fontFamily: "'JetBrains Mono', Consolas, monospace",
          fontLigatures: true,
          lineNumbersMinChars: 3,
          scrollBeyondLastLine: false,
          smoothScrolling: true,
          padding: { top: 14, bottom: 14 },
          glyphMargin: Boolean(findings?.length),
          renderLineHighlight: readOnly ? "none" : "line",
          automaticLayout: true,
          tabSize: 4,
          wordWrap: "off",
          scrollbar: { verticalScrollbarSize: 10, horizontalScrollbarSize: 10 },
        }}
      />
    </div>
  );
});

export function CodeDiff({ original, modified, language, height = 420 }: { original: string; modified: string; language: Language; height?: number | string }) {
  const theme = useResolvedTheme();
  const diffRef = useRef<monaco.editor.IStandaloneDiffEditor | null>(null);
  // @monaco-editor/react disposes the models before resetting the widget on unmount, which throws.
  // Keep the models, then detach and dispose them ourselves in the right order.
  useEffect(() => () => {
    const ed = diffRef.current;
    if (!ed) return;
    const m = ed.getModel();
    ed.setModel(null);
    m?.original.dispose();
    m?.modified.dispose();
  }, []);
  return (
    <div className="overflow-hidden rounded-lg border border-border" style={{ height }}>
      <DiffEditor
        keepCurrentOriginalModel
        keepCurrentModifiedModel
        onMount={(ed) => { diffRef.current = ed; }}
        height="100%"
        language={langMonaco(language)}
        original={original}
        modified={modified}
        theme={theme === "light" ? "devpilot-light" : "devpilot-dark"}
        loading={<Loading />}
        options={{
          readOnly: true,
          originalEditable: false,
          renderSideBySide: true,
          useInlineViewWhenSpaceIsLimited: true,
          renderSideBySideInlineBreakpoint: 760,
          minimap: { enabled: false },
          fontSize: 13,
          fontFamily: "'JetBrains Mono', Consolas, monospace",
          scrollBeyondLastLine: false,
          automaticLayout: true,
          padding: { top: 10 },
        }}
      />
    </div>
  );
}

/** IDE-style window chrome around an editor: traffic lights, file tab, language chip and actions. */
export function EditorFrame({ filename, language, right, children, footer }: { filename: React.ReactNode; language?: string; right?: React.ReactNode; children: React.ReactNode; footer?: React.ReactNode }) {
  return (
    <div className="card overflow-hidden">
      <div className="flex h-11 items-center gap-3 border-b border-border bg-surface-2 px-3">
        <div className="flex gap-1.5" aria-hidden>
          <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]/80" /><span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]/80" /><span className="h-2.5 w-2.5 rounded-full bg-[#28c840]/80" />
        </div>
        <div className="flex h-full min-w-0 items-center gap-2 border-x border-border border-t-2 border-t-accent bg-surface px-3">
          <span className="truncate font-mono text-[12px] text-text">{filename}</span>
          {language && <span className="rounded bg-surface-3 px-1.5 py-px font-mono text-[10px] text-subtle">{language}</span>}
        </div>
        <div className="ml-auto flex items-center gap-1.5">{right}</div>
      </div>
      {children}
      {footer && <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border bg-surface-2 px-3 py-1.5 font-mono text-[10.5px] text-subtle">{footer}</div>}
    </div>
  );
}
