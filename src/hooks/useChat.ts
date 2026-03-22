import { useCallback, useRef, useState } from "react";
import type {
  BackendEvent,
  ChatMessage,
  ConfigLoadedEvent,
  ContextEvent,
  PromptEvent,
  RewindCompleteEvent,
  ToolCallInfo,
} from "../protocol/types.js";
import {
  isCallEnded,
  isConfigLoaded,
  isContext,
  isError,
  isPrompt,
  isRewindComplete,
  isStateChanged,
  isStreamChunk,
  isStreamEnd,
  isStreamStart,
  isToolCalls,
} from "../protocol/events.js";

let msgCounter = 0;
function nextId(): string {
  return `msg_${++msgCounter}`;
}

/**
 * Manages chat message state and streaming buffer.
 * Returns a handler to feed BackendEvents into.
 */
export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streamingText, setStreamingText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentState, setCurrentState] = useState("");
  const [callId, setCallId] = useState("");
  const [configSource, setConfigSource] = useState("");
  const [callEnded, setCallEnded] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const [finalTranscript, setFinalTranscript] = useState<
    Record<string, unknown>[] | null
  >(null);
  // Overlay data for context/prompt viewers
  const [contextData, setContextData] = useState<Record<string, unknown>[] | null>(null);
  const [promptData, setPromptData] = useState<{
    prompt: string;
    state: string;
    dynamicVars: Record<string, unknown>;
  } | null>(null);

  // Accumulate streaming text in a ref for the commit
  const streamBuf = useRef("");
  // Track current state in a ref so handleEvent (stable callback) can read it
  const currentStateRef = useRef("");

  const addUserMessage = useCallback((text: string) => {
    const msg: ChatMessage = {
      id: nextId(),
      role: "user",
      content: text,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, msg]);
  }, []);

  const handleEvent = useCallback((event: BackendEvent) => {
    if (isConfigLoaded(event)) {
      const cle = event as ConfigLoadedEvent;
      setCallId(cle.call_id);
      setConfigSource(cle.config_source);
      setCurrentState(cle.starting_state);
      currentStateRef.current = cle.starting_state;

      // Display loaded messages from a session/chat export
      if (cle.loaded_messages && cle.loaded_messages.length > 0) {
        const loaded: ChatMessage[] = [];
        for (const m of cle.loaded_messages) {
          if (m.content || m.tool_calls) {
            loaded.push({
              id: nextId(),
              role: m.role,
              content: m.content || "",
              timestamp: Date.now(),
              toolCalls: m.tool_calls,
            });
          }
        }
        // On resume, we want the transcript to appear BEFORE any newly-streamed
        // assistant continuation. The backend emits config_loaded before streaming,
        // so it's safe (and correct) to replace the list here.
        setMessages(loaded);
      }
    } else if (isStreamStart(event)) {
      setIsStreaming(true);
      streamBuf.current = "";
      setStreamingText("");
    } else if (isStreamChunk(event)) {
      streamBuf.current += event.text;
      setStreamingText(streamBuf.current);
    } else if (isStreamEnd(event)) {
      setIsStreaming(false);
      const text = streamBuf.current;
      if (text) {
        const msg: ChatMessage = {
          id: nextId(),
          role: "assistant",
          content: text,
          timestamp: Date.now(),
        };
        setMessages((prev) => [...prev, msg]);
      }
      setStreamingText("");
      streamBuf.current = "";
    } else if (isToolCalls(event)) {
      // Tool calls must be added as a NEW entry (not modify existing) because
      // Ink's <Static> component only renders items once and never re-renders
      // items with the same key.
      const msg: ChatMessage = {
        id: nextId(),
        role: "assistant",
        content: "",
        timestamp: Date.now(),
        toolCalls: event.tool_calls,
      };
      setMessages((prev) => [...prev, msg]);
    } else if (isStateChanged(event)) {
      setCurrentState(event.state);
      currentStateRef.current = event.state;
    } else if (isContext(event)) {
      setContextData((event as ContextEvent).messages);
    } else if (isPrompt(event)) {
      const pe = event as PromptEvent;
      setPromptData({
        prompt: pe.prompt,
        state: pe.state,
        dynamicVars: pe.dynamic_vars,
      });
    } else if (isCallEnded(event)) {
      setCallEnded(true);
      setFinalTranscript(event.transcript);
    } else if (isRewindComplete(event)) {
      const rce = event as RewindCompleteEvent;
      const loaded: ChatMessage[] = [];
      for (const m of rce.loaded_messages) {
        if (m.content || m.tool_calls) {
          loaded.push({
            id: nextId(),
            role: m.role,
            content: m.content || "",
            timestamp: Date.now(),
            toolCalls: m.tool_calls,
          });
        }
      }
      setMessages(loaded);
      setCurrentState(rce.current_state);
      currentStateRef.current = rce.current_state;
    } else if (isError(event)) {
      setLastError(event.message);
    }
  }, []);

  const clearError = useCallback(() => setLastError(null), []);
  const clearContext = useCallback(() => setContextData(null), []);

  return {
    messages,
    streamingText,
    isStreaming,
    currentState,
    callId,
    configSource,
    callEnded,
    lastError,
    finalTranscript,
    contextData,
    promptData,
    addUserMessage,
    handleEvent,
    clearError,
    clearContext,
  };
}
