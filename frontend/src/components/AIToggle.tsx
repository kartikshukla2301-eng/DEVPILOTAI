import { Link } from "react-router-dom";
import { Cpu, Sparkles } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { Toggle } from "./ui";

/** Per-run AI switch. Disabled with an explanation when the server has no AI key or the user turned AI off. */
export function AIToggle({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  const { aiStatus, settings } = useAuth();
  if (!aiStatus?.ai_configured) {
    return (
      <Link to="/settings#ai" className="inline-flex items-center gap-1.5 rounded-full border border-blue/30 bg-blue-soft px-2.5 py-1 text-xs font-medium text-blue" title="No AI API key is configured on the server">
        <Cpu className="h-3.5 w-3.5" /> Local analysis mode
      </Link>
    );
  }
  if (!settings.use_ai) {
    return (
      <Link to="/settings#ai" className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-2 px-2.5 py-1 text-xs font-medium text-muted" title="AI is turned off in your settings">
        <Cpu className="h-3.5 w-3.5" /> AI disabled in settings
      </Link>
    );
  }
  return <Toggle checked={value} onChange={onChange} label={<span className="flex items-center gap-1.5 text-[13px]"><Sparkles className="h-3.5 w-3.5 text-accent" /> Use AI</span>} />;
}
