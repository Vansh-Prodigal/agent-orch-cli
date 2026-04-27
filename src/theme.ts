/**
 * Vercel Geist-inspired palette — monochromatic base, purposeful color.
 * Designed for dark terminal backgrounds.
 */
export const theme = {
  /** Vercel blue — primary UI, headings, assistant accent */
  primary: "#3291ff",
  /** Geist green — user messages, success, confirmations */
  success: "#62c073",
  /** Geist amber — warnings, batch mode, state labels */
  warning: "#f5a623",
  /** Geist red — errors, critical alerts */
  error: "#ff6066",
  /** Vercel blue (lighter) — info panels, context viewer */
  info: "#51a8ff",
  /** Geist purple — tool calls, streaming indicator, special accents */
  accent: "#be79f0",
  /** Lighter lilac — transitions into builtin states */
  builtin: "#d4a3ff",
  /** Gray-600 — secondary/muted text */
  muted: "#888888",
  /** Gray-1000 — strong emphasis, body text */
  emphasis: "#ededed",
  /** Accents-2 — borders, separators, faint elements */
  border: "#333333",
} as const;

export type ThemeColor = (typeof theme)[keyof typeof theme];

/** Unicode glyphs for UI chrome. */
export const glyph = {
  diamond: "\u25C6",    // ◆
  diamondD: "\u25C8",   // ◈
  arrow: "\u25B8",      // ▸
  bullet: "\u25CF",     // ●
  bulletO: "\u25CB",    // ○
  prompt: "\u276F",     // ❯
  sep: "\u2502",        // │
  block: "\u258C",      // ▌
  gear: "\u27D0",       // ⟐
  check: "\u2713",      // ✓
  cross: "\u2717",      // ✗
  dot: "\u00B7",        // ·
  star: "\u2726",       // ✦
  cursor: "\u258B",     // ▋
  ellipsis: "\u2026",   // …
} as const;
