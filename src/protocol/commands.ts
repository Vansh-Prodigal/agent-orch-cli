import type {
  Command,
  EndCallCommand,
  GetContextCommand,
  GetPromptCommand,
  GetStateCommand,
  GetTranscriptCommand,
  LoadConfigCommand,
  LoadConfigFileCommand,
  LoadSessionCommand,
  SendMessageCommand,
  ShutdownCommand,
} from "./types.js";

export function loadConfig(
  toNumber: string,
  opts?: {
    fromNumber?: string;
    callDirection?: "inbound" | "outbound";
    configOverrides?: Record<string, unknown>;
  },
): LoadConfigCommand {
  return {
    command: "load_config",
    to_number: toNumber,
    ...(opts?.fromNumber && { from_number: opts.fromNumber }),
    ...(opts?.callDirection && { call_direction: opts.callDirection }),
    ...(opts?.configOverrides && { config_overrides: opts.configOverrides }),
  };
}

export function loadConfigFile(path: string): LoadConfigFileCommand {
  return { command: "load_config_file", path };
}

export function loadSession(
  path: string,
  opts?: { configPath?: string; toNumber?: string; fromNumber?: string },
): LoadSessionCommand {
  return {
    command: "load_session",
    path,
    ...(opts?.configPath && { config_path: opts.configPath }),
    ...(opts?.toNumber && { to_number: opts.toNumber }),
    ...(opts?.fromNumber && { from_number: opts.fromNumber }),
  };
}

export function sendMessage(text: string): SendMessageCommand {
  return { command: "send_message", text };
}

export function getState(): GetStateCommand {
  return { command: "get_state" };
}

export function getTranscript(): GetTranscriptCommand {
  return { command: "get_transcript" };
}

export function getContext(): GetContextCommand {
  return { command: "get_context" };
}

export function getPrompt(): GetPromptCommand {
  return { command: "get_prompt" };
}

export function endCall(): EndCallCommand {
  return { command: "end_call" };
}

export function shutdown(): ShutdownCommand {
  return { command: "shutdown" };
}

export function serialize(cmd: Command): string {
  return JSON.stringify(cmd);
}
