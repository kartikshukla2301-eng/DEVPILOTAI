import { useState } from "react";
import { Download } from "lucide-react";
import { downloadFromApi, saveText } from "../../lib/api";
import type { DocsResult } from "../../lib/types";
import { Markdown } from "../Markdown";
import { Alert, Badge, Button, Card, CopyButton, ModeBadge, Segmented } from "../ui";

export function DocsResults({ result, name = "documentation" }: { result: DocsResult; name?: string }) {
  const [view, setView] = useState<"preview" | "markdown">("preview");
  const file = (name.replace(/\.[^.]+$/, "").replace(/[^\w.-]+/g, "_") || "documentation") + ".md";
  return (
    <Card padded={false}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <Segmented size="sm" value={view} onChange={setView} options={[{ value: "preview", label: "Preview" }, { value: "markdown", label: "Markdown" }]} />
          <ModeBadge ai={result.ai_used} error={result.ai_error} />
          {Object.entries(result.symbols).filter(([, v]) => v > 0).map(([k, v]) => <Badge key={k}>{v} {k}</Badge>)}
        </div>
        <div className="flex gap-2">
          <CopyButton text={result.markdown} label="Copy Markdown" />
          <Button size="sm" icon={<Download className="h-3.5 w-3.5" />}
            onClick={() => (result.id ? downloadFromApi(`/documentation/history/${result.id}/download`, file) : saveText(result.markdown, file, "text/markdown"))}>
            Download .md
          </Button>
        </div>
      </div>
      <div className="p-5">
        {result.ai_error && <div className="mb-4"><Alert tone="warning" title="AI unavailable">{result.ai_error}. Showing locally generated documentation.</Alert></div>}
        {view === "preview" ? (
          <div className="max-h-[70vh] overflow-y-auto pr-1"><Markdown>{result.markdown}</Markdown></div>
        ) : (
          <pre className="max-h-[70vh] overflow-auto rounded-lg border border-border bg-bg p-4 font-mono text-xs leading-relaxed">{result.markdown}</pre>
        )}
      </div>
    </Card>
  );
}
