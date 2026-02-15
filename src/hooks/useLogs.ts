import { writeFileSync } from "node:fs";
import { useCallback, useRef, useState } from "react";

const MAX_LINES = 1000;

/**
 * Captures stderr lines from the Python backend.
 * Maintains a rolling buffer and exposes helpers.
 */
export function useLogs() {
  const [lines, setLines] = useState<string[]>([]);
  const buffer = useRef<string[]>([]);

  const addLine = useCallback((line: string) => {
    buffer.current.push(line);
    if (buffer.current.length > MAX_LINES) {
      buffer.current = buffer.current.slice(-MAX_LINES);
    }
    // Only update React state periodically to avoid re-render storms
    setLines([...buffer.current]);
  }, []);

  const dumpToFile = useCallback((path: string) => {
    writeFileSync(path, buffer.current.join("\n") + "\n", "utf-8");
  }, []);

  const clear = useCallback(() => {
    buffer.current = [];
    setLines([]);
  }, []);

  return { lines, addLine, dumpToFile, clear };
}
