// ---------------------------------------------------------------------------
// Commands (Ink → Python via stdin)
// ---------------------------------------------------------------------------

export interface LoadConfigCommand {
  command: "load_config";
  to_number: string;
  from_number?: string;
  call_direction?: "inbound" | "outbound";
  config_overrides?: Record<string, unknown>;
}

export interface LoadConfigFileCommand {
  command: "load_config_file";
  path: string;
}

export interface LoadSessionCommand {
  command: "load_session";
  path: string;
  config_path?: string;
  to_number?: string;
  from_number?: string;
}

export interface SendMessageCommand {
  command: "send_message";
  text: string;
}

export interface GetStateCommand {
  command: "get_state";
}

export interface GetTranscriptCommand {
  command: "get_transcript";
}

export interface GetContextCommand {
  command: "get_context";
}

export interface GetPromptCommand {
  command: "get_prompt";
}

export interface EndCallCommand {
  command: "end_call";
}

export interface ShutdownCommand {
  command: "shutdown";
}

export interface RewindCommand {
  command: "rewind";
  index: number;
}

export type Command =
  | LoadConfigCommand
  | LoadConfigFileCommand
  | LoadSessionCommand
  | SendMessageCommand
  | GetStateCommand
  | GetTranscriptCommand
  | GetContextCommand
  | GetPromptCommand
  | EndCallCommand
  | ShutdownCommand
  | RewindCommand;

// ---------------------------------------------------------------------------
// Events (Python → Ink via stdout)
// ---------------------------------------------------------------------------

export interface ReadyEvent {
  event: "ready";
  version: string;
}

export interface LoadedMessage {
  role: "user" | "assistant";
  content: string;
  tool_calls?: ToolCallInfo[];
}

export interface ConfigLoadedEvent {
  event: "config_loaded";
  call_id: string;
  config_source: "remote" | "local" | "merged" | "session";
  starting_state: string;
  first_message: string;
  config: Record<string, unknown>;
  loaded_messages?: LoadedMessage[];
  dynamic_prompt_index?: number | null;
  dynamic_prompt_condition?: string | null;
}

export interface StreamStartEvent {
  event: "stream_start";
}

export interface StreamChunkEvent {
  event: "stream_chunk";
  text: string;
}

export interface StreamEndEvent {
  event: "stream_end";
}

export interface ToolCallInfo {
  tool_call_id: string;
  name: string;
  arguments: string;
  result: string;
}

export interface ToolCallsEvent {
  event: "tool_calls";
  tool_calls: ToolCallInfo[];
}

export interface StateChangedEvent {
  event: "state_changed";
  state: string;
  dynamic_prompt_index?: number | null;
  dynamic_prompt_condition?: string | null;
}

export interface ContextEvent {
  event: "context";
  messages: Record<string, unknown>[];
  dynamic_vars?: Record<string, unknown>;
  current_state?: string;
}

export interface PromptEvent {
  event: "prompt";
  prompt: string;
  state: string;
  dynamic_vars: Record<string, unknown>;
}

export interface CallEndedEvent {
  event: "call_ended";
  transcript: Record<string, unknown>[];
}

export interface TranscriptEvent {
  event: "transcript";
  transcript: Record<string, unknown>[];
}

export interface ErrorEvent {
  event: "error";
  message: string;
  code?: string;
}

export interface RewindCompleteEvent {
  event: "rewind_complete";
  loaded_messages: LoadedMessage[];
  current_state: string;
  dynamic_vars: Record<string, unknown>;
}

export interface ShutdownAckEvent {
  event: "shutdown_ack";
}

export type BackendEvent =
  | ReadyEvent
  | ConfigLoadedEvent
  | StreamStartEvent
  | StreamChunkEvent
  | StreamEndEvent
  | ToolCallsEvent
  | StateChangedEvent
  | ContextEvent
  | PromptEvent
  | CallEndedEvent
  | TranscriptEvent
  | ErrorEvent
  | RewindCompleteEvent
  | ShutdownAckEvent;

// ---------------------------------------------------------------------------
// Chat message types (UI-side)
// ---------------------------------------------------------------------------

export type MessageRole = "user" | "assistant" | "system";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
  toolCalls?: ToolCallInfo[];
}

// ---------------------------------------------------------------------------
// Session file format
// ---------------------------------------------------------------------------

export interface SessionFile {
  version: string;
  callId: string;
  configSource: string;
  config: Record<string, unknown>;
  messages: ChatMessage[];
  transcript: Record<string, unknown>[];
  currentState: string;
  savedAt: string;
}
