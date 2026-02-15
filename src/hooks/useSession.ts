import { readFileSync, writeFileSync } from "node:fs";
import { useCallback } from "react";
import type { ChatMessage, SessionFile } from "../protocol/types.js";

const SESSION_VERSION = "1.0.0";

export interface SaveSessionOpts {
  callId: string;
  configSource: string;
  config: Record<string, unknown>;
  messages: ChatMessage[];
  transcript: Record<string, unknown>[];
  currentState: string;
}

/**
 * Save and load session files for resuming conversations.
 */
export function useSession() {
  const save = useCallback((path: string, opts: SaveSessionOpts) => {
    const data: SessionFile = {
      version: SESSION_VERSION,
      callId: opts.callId,
      configSource: opts.configSource,
      config: opts.config,
      messages: opts.messages,
      transcript: opts.transcript,
      currentState: opts.currentState,
      savedAt: new Date().toISOString(),
    };
    writeFileSync(path, JSON.stringify(data, null, 2), "utf-8");
  }, []);

  const load = useCallback((path: string): SessionFile | null => {
    try {
      const raw = readFileSync(path, "utf-8");
      return JSON.parse(raw) as SessionFile;
    } catch {
      return null;
    }
  }, []);

  return { save, load };
}
