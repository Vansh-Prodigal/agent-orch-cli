/**
 * Bright color palette for the CLI.
 * Uses chalk bright ANSI color names for better visibility.
 */
export const theme = {
  /** Headings, titles, primary UI (e.g. "ProAgent CLI") */
  primary: "cyanBright",
  /** Success state, confirmations, prompts */
  success: "greenBright",
  /** Warnings, batch mode, optional labels */
  warning: "yellowBright",
  /** Errors */
  error: "redBright",
  /** Info panels (e.g. context viewer) */
  info: "blueBright",
  /** Tool calls, special blocks */
  accent: "magentaBright",
  /** Muted / secondary text (use with dimColor for hints) */
  muted: "gray",
  /** Strong labels (e.g. "Assembled Prompt") */
  emphasis: "whiteBright",
} as const;

export type ThemeColor = (typeof theme)[keyof typeof theme];
