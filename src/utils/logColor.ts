import { theme } from "../theme.js";

export function logColor(line: string): string {
  const upper = line.toUpperCase();
  if (upper.includes("ERROR") || upper.includes("CRITICAL")) return theme.error;
  if (upper.includes("WARNING") || upper.includes("WARN")) return theme.warning;
  if (upper.includes("INFO")) return theme.info;
  if (upper.includes("DEBUG")) return theme.success;
  return theme.muted;
}
