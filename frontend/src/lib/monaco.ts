/**
 * Bundle Monaco locally (no CDN) so the editor works offline and under a strict CSP.
 */
import * as monaco from "monaco-editor";
import { loader } from "@monaco-editor/react";
// The package "exports" map resolves "monaco-editor/<path>" to "esm/vs/<path>.js".
import EditorWorker from "monaco-editor/editor/editor.worker?worker";
import TsWorker from "monaco-editor/language/typescript/ts.worker?worker";

self.MonacoEnvironment = {
  getWorker(_id: string, label: string) {
    if (label === "typescript" || label === "javascript") return new TsWorker();
    return new EditorWorker();
  },
};

monaco.editor.defineTheme("devpilot-dark", {
  base: "vs-dark",
  inherit: true,
  rules: [
    { token: "comment", foreground: "6b7394", fontStyle: "italic" },
    { token: "keyword", foreground: "b69cff" },
    { token: "string", foreground: "8bd5a0" },
    { token: "number", foreground: "f2b179" },
    { token: "type", foreground: "7cb7ff" },
  ],
  colors: {
    "editor.background": "#0d1325",
    "editor.lineHighlightBackground": "#161d35",
    "editorLineNumber.foreground": "#3d4766",
    "editorLineNumber.activeForeground": "#8a93ab",
    "editorGutter.background": "#0d1325",
    "editor.selectionBackground": "#7c5cff40",
    "editorIndentGuide.background1": "#1d2542",
    "editorWidget.background": "#10162a",
    "editorWidget.border": "#232c4a",
    "diffEditor.insertedTextBackground": "#22c55e22",
    "diffEditor.removedTextBackground": "#ef444422",
    "scrollbarSlider.background": "#2f3a5e80",
  },
});

monaco.editor.defineTheme("devpilot-light", {
  base: "vs",
  inherit: true,
  rules: [{ token: "comment", foreground: "8a92a8", fontStyle: "italic" }],
  colors: {
    "editor.background": "#fbfcfe",
    "editor.lineHighlightBackground": "#f1f3f9",
    "editorLineNumber.foreground": "#b5bccd",
    "editor.selectionBackground": "#6545f030",
  },
});

// Analysis is done by the backend; keep the in-editor TS diagnostics from adding noise to arbitrary snippets.
// Monaco >= 0.55 exposes this as the top-level `monaco.typescript` namespace (the old
// `monaco.languages.typescript` is a deprecated stub); its typings lag behind, hence the narrow cast.
type Diagnostics = { setDiagnosticsOptions(o: { noSemanticValidation?: boolean; noSyntaxValidation?: boolean }): void };
const tsApi = (monaco as unknown as { typescript?: { typescriptDefaults?: Diagnostics; javascriptDefaults?: Diagnostics } }).typescript;
tsApi?.typescriptDefaults?.setDiagnosticsOptions({ noSemanticValidation: true, noSyntaxValidation: false });
tsApi?.javascriptDefaults?.setDiagnosticsOptions({ noSemanticValidation: true, noSyntaxValidation: false });

loader.config({ monaco });

export { monaco };
