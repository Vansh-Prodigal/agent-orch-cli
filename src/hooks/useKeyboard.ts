import { useInput } from "ink";

export interface KeyboardActions {
  onExport: () => void;
  onToggleLogs: () => void;
  onSaveSession: () => void;
  onEndCall: () => void;
  onEscape: () => void;
  onShowContext: () => void;
  onShowPrompt: () => void;
  onToggleBatch: () => void;
  enabled: boolean;
}

/**
 * Binds keyboard shortcuts.
 *
 * Ctrl+E  -> export chat transcript (LLM format) to file
 * Ctrl+L  -> toggle log viewer
 * Ctrl+S  -> save session to file
 * Ctrl+X  -> show chat context overlay
 * Ctrl+P  -> export prompt to markdown file
 * Ctrl+B  -> toggle batch input mode
 * Escape  -> close overlay / cancel
 */
export function useKeyboard({
  onExport,
  onToggleLogs,
  onSaveSession,
  onEndCall,
  onEscape,
  onShowContext,
  onShowPrompt,
  onToggleBatch,
  enabled,
}: KeyboardActions) {
  useInput(
    (input, key) => {
      if (!enabled) return;

      if (key.ctrl && input === "e") {
        onExport();
      } else if (key.ctrl && input === "l") {
        onToggleLogs();
      } else if (key.ctrl && input === "s") {
        onSaveSession();
      } else if (key.ctrl && input === "x") {
        onShowContext();
      } else if (key.ctrl && input === "p") {
        onShowPrompt();
      } else if (key.ctrl && input === "b") {
        onToggleBatch();
      } else if (key.escape) {
        onEscape();
      }
    },
    { isActive: enabled },
  );
}
