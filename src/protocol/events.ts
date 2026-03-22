import type {
  BackendEvent,
  CallEndedEvent,
  ConfigLoadedEvent,
  ContextEvent,
  ErrorEvent,
  PromptEvent,
  ReadyEvent,
  RewindCompleteEvent,
  ShutdownAckEvent,
  StateChangedEvent,
  StreamChunkEvent,
  StreamEndEvent,
  StreamStartEvent,
  ToolCallsEvent,
  TranscriptEvent,
} from "./types.js";

export function parseEvent(line: string): BackendEvent | null {
  try {
    const data = JSON.parse(line);
    if (typeof data === "object" && data !== null && typeof data.event === "string") {
      return data as BackendEvent;
    }
    return null;
  } catch {
    return null;
  }
}

// Type guards

export function isReady(e: BackendEvent): e is ReadyEvent {
  return e.event === "ready";
}

export function isConfigLoaded(e: BackendEvent): e is ConfigLoadedEvent {
  return e.event === "config_loaded";
}

export function isStreamStart(e: BackendEvent): e is StreamStartEvent {
  return e.event === "stream_start";
}

export function isStreamChunk(e: BackendEvent): e is StreamChunkEvent {
  return e.event === "stream_chunk";
}

export function isStreamEnd(e: BackendEvent): e is StreamEndEvent {
  return e.event === "stream_end";
}

export function isToolCalls(e: BackendEvent): e is ToolCallsEvent {
  return e.event === "tool_calls";
}

export function isStateChanged(e: BackendEvent): e is StateChangedEvent {
  return e.event === "state_changed";
}

export function isContext(e: BackendEvent): e is ContextEvent {
  return e.event === "context";
}

export function isPrompt(e: BackendEvent): e is PromptEvent {
  return e.event === "prompt";
}

export function isCallEnded(e: BackendEvent): e is CallEndedEvent {
  return e.event === "call_ended";
}

export function isTranscript(e: BackendEvent): e is TranscriptEvent {
  return e.event === "transcript";
}

export function isError(e: BackendEvent): e is ErrorEvent {
  return e.event === "error";
}

export function isRewindComplete(e: BackendEvent): e is RewindCompleteEvent {
  return e.event === "rewind_complete";
}

export function isShutdownAck(e: BackendEvent): e is ShutdownAckEvent {
  return e.event === "shutdown_ack";
}
