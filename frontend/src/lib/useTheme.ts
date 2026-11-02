import { useEffect, useState } from "react";

/** Resolved theme ("dark" | "light") from the <html> class, reacting to changes. */
export function useResolvedTheme(): "dark" | "light" {
  const get = () => (document.documentElement.classList.contains("light") ? "light" : "dark");
  const [theme, setTheme] = useState<"dark" | "light">(get);
  useEffect(() => {
    const obs = new MutationObserver(() => setTheme(get()));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => obs.disconnect();
  }, []);
  return theme;
}
