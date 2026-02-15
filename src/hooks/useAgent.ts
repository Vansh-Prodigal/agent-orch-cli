import { execSync, spawn, type ChildProcess } from "node:child_process";
import { existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { createInterface } from "node:readline";
import { useCallback, useEffect, useRef, useState } from "react";
import { parseEvent } from "../protocol/events.js";
import type { BackendEvent, Command } from "../protocol/types.js";

export interface UseAgentOptions {
  pythonPath?: string;
  cwd?: string;
  onEvent: (event: BackendEvent) => void;
  onStderr: (line: string) => void;
  onExit: (code: number | null) => void;
}

/**
 * Spawns the Python cli_backend.py subprocess and provides JSON-line I/O.
 */
export function useAgent({
  pythonPath,
  cwd,
  onEvent,
  onStderr,
  onExit,
}: UseAgentOptions) {
  const [ready, setReady] = useState(false);
  const procRef = useRef<ChildProcess | null>(null);
  const onEventRef = useRef(onEvent);
  const onStderrRef = useRef(onStderr);
  const onExitRef = useRef(onExit);

  // Keep refs up to date
  onEventRef.current = onEvent;
  onStderrRef.current = onStderr;
  onExitRef.current = onExit;

  useEffect(() => {
    const python = resolvePython(pythonPath, cwd);
    const backendPath = resolveBackendPath(cwd);
    const agentDir = resolveAgentDir(cwd);

    const proc = spawn(python, [backendPath], {
      cwd: agentDir,
      stdio: ["pipe", "pipe", "pipe"],
      env: { ...process.env },
    });

    procRef.current = proc;

    // Read stdout line-by-line for JSON events
    if (proc.stdout) {
      const rl = createInterface({ input: proc.stdout });
      rl.on("line", (line) => {
        const event = parseEvent(line);
        if (event) {
          if (event.event === "ready") {
            setReady(true);
          }
          onEventRef.current(event);
        }
      });
    }

    // Read stderr line-by-line for logs
    if (proc.stderr) {
      const rl = createInterface({ input: proc.stderr });
      rl.on("line", (line) => {
        onStderrRef.current(line);
      });
    }

    proc.on("exit", (code) => {
      procRef.current = null;
      setReady(false);
      onExitRef.current(code);
    });

    proc.on("error", (err) => {
      onStderrRef.current(`[spawn error] ${err.message}`);
      procRef.current = null;
      setReady(false);
    });

    return () => {
      if (proc.exitCode === null) {
        proc.kill("SIGTERM");
      }
    };
  }, [pythonPath, cwd]);

  const sendCommand = useCallback((cmd: Command) => {
    const proc = procRef.current;
    if (proc && proc.stdin && !proc.stdin.destroyed) {
      proc.stdin.write(JSON.stringify(cmd) + "\n");
    }
  }, []);

  const kill = useCallback(() => {
    const proc = procRef.current;
    if (proc && proc.exitCode === null) {
      proc.kill("SIGTERM");
    }
  }, []);

  return { ready, sendCommand, kill };
}

// ---------------------------------------------------------------------------
// Helpers to locate Python and the backend script
// ---------------------------------------------------------------------------

function resolveProjectRoot(cwd?: string): string {
  if (cwd) return cwd;
  // If running from cli/, go up one level
  const fromCwd = process.cwd();
  if (fromCwd.endsWith("/cli") || fromCwd.endsWith("\\cli")) {
    return resolve(fromCwd, "..");
  }
  // If running from project root
  if (existsSync(join(fromCwd, "agent_orchestrator"))) {
    return fromCwd;
  }
  return resolve(fromCwd, "..");
}

function resolvePython(explicit?: string, projectRoot?: string): string {
  if (explicit) return explicit;
  if (process.env["PROAGENT_PYTHON"]) return process.env["PROAGENT_PYTHON"];

  const root = resolveProjectRoot(projectRoot);

  // Try common venv locations relative to project root
  const venvNames = [
    "agent-orch",
    "venv",
    ".venv",
    "agent_orch",
    "env",
  ];
  for (const name of venvNames) {
    const candidate = join(root, name, "bin", "python3");
    if (existsSync(candidate)) {
      return candidate;
    }
  }

  // Fallback: try system python
  const systemCandidates = ["python3", "python"];
  for (const c of systemCandidates) {
    try {
      execSync(`${c} --version`, { stdio: "ignore" });
      return c;
    } catch {
      // continue
    }
  }
  return "python3";
}

function resolveBackendPath(cwd?: string): string {
  const base = resolveProjectRoot(cwd);
  return join(base, "cli", "backend.py");
}

function resolveAgentDir(cwd?: string): string {
  const base = resolveProjectRoot(cwd);
  return join(base, "agent_orchestrator");
}
