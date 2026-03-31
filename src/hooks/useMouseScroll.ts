import { useEffect, useRef } from "react";
import { useStdin, useStdout } from "ink";
import type { StdinProps } from "ink";

// Matches any SGR mouse sequence (clicks, releases, wheel, drag)
const MOUSE_SGR_RE = /\x1b\[<\d+;\d+;\d+[Mm]/g;

/**
 * Enables SGR mouse tracking and intercepts all mouse escape
 * sequences via Ink's internal event emitter so they never reach
 * useInput or the text input. Wheel events are translated into
 * scroll callbacks; everything else is silently stripped.
 *
 * Note: while mouse tracking is active, hold Shift to select text
 * (standard terminal convention, same as vim/tmux/less).
 */
export function useMouseScroll(
  onScroll: (delta: number) => void,
  isActive = true,
  scrollSpeed = 3,
): void {
  const { stdout } = useStdout();
  const stdinCtx = useStdin() as StdinProps;
  const emitter = stdinCtx.internal_eventEmitter;
  const callbackRef = useRef(onScroll);
  callbackRef.current = onScroll;

  useEffect(() => {
    if (!isActive || !stdout || !emitter) return;

    // Enable basic mouse button tracking + SGR extended coordinate mode
    stdout.write("\x1b[?1000h\x1b[?1006h");

    const originalEmit = emitter.emit.bind(emitter);
    emitter.emit = (event: string | symbol, ...args: unknown[]): boolean => {
      if (event === "input" && typeof args[0] === "string") {
        const str = args[0];

        // Handle wheel events: button 64 = scroll up, 65 = scroll down
        for (const match of str.matchAll(/\x1b\[<(\d+);\d+;\d+[Mm]/g)) {
          const btn = parseInt(match[1], 10);
          if (btn === 64) callbackRef.current(-scrollSpeed);
          else if (btn === 65) callbackRef.current(scrollSpeed);
        }

        // Strip ALL mouse sequences so clicks/drags don't pollute input
        const cleaned = str.replace(MOUSE_SGR_RE, "");
        if (cleaned.length === 0) return true;

        return originalEmit(event, cleaned);
      }
      return originalEmit(event, ...args);
    };

    const disableMouse = () => stdout.write("\x1b[?1000l\x1b[?1006l");
    process.on("exit", disableMouse);

    return () => {
      emitter.emit = originalEmit;
      disableMouse();
      process.removeListener("exit", disableMouse);
    };
  }, [isActive, stdout, emitter, scrollSpeed]);
}
