import { useEffect } from "react";
import { useStdout } from "ink";

/**
 * Enables terminal Alternate Scroll Mode so that mouse wheel
 * events are translated into Up/Down arrow key sequences.
 *
 * This avoids full mouse tracking entirely, so text selection
 * and all other native mouse interactions remain functional.
 */
export function useMouseScroll(isActive = true): void {
  const { stdout } = useStdout();

  useEffect(() => {
    if (!isActive || !stdout) return;

    // Alternate Scroll Mode: wheel events → arrow key sequences
    stdout.write("\x1b[?1007h");

    const disable = () => stdout.write("\x1b[?1007l");
    process.on("exit", disable);

    return () => {
      disable();
      process.removeListener("exit", disable);
    };
  }, [isActive, stdout]);
}
