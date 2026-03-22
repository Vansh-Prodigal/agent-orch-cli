import React, { useEffect, useRef, useState } from "react";
import { Box, Text, useInput, useStdout } from "ink";
import { ScrollView } from "ink-scroll-view";
import type { ScrollViewRef } from "ink-scroll-view";
import type { ChatMessage } from "../protocol/types.js";
import { theme } from "../theme.js";
import { MessageBubble } from "./MessageBubble.js";
import { ToolCallDisplay } from "./ToolCallDisplay.js";
import { ContextViewer } from "./ContextViewer.js";
import { InputBar } from "./InputBar.js";
import { StatusBar } from "./StatusBar.js";

interface Props {
  messages: ChatMessage[];
  streamingText: string;
  isStreaming: boolean;
  currentState: string;
  callId: string;
  configSource: string;
  onSendMessage: (text: string) => void;
  inputDisabled: boolean;
  batchMode: boolean;
  batchLines: string[];
  onBatchAdd: (line: string) => void;
  onBatchSend: () => void;
  // Overlay state
  showContext: boolean;
  promptData: { prompt: string; state: string; dynamicVars: Record<string, unknown> } | null;
  rewindMode?: boolean;
}

export function ChatView({
  messages,
  streamingText,
  isStreaming,
  currentState,
  callId,
  configSource,
  onSendMessage,
  inputDisabled,
  batchMode,
  batchLines,
  onBatchAdd,
  onBatchSend,
  showContext,
  promptData,
  rewindMode,
}: Props) {
  const scrollRef = useRef<ScrollViewRef>(null);
  const { stdout } = useStdout();
  const [termHeight, setTermHeight] = useState(stdout?.rows ?? 24);

  // Auto-scroll to bottom on new messages or streaming updates
  useEffect(() => {
    scrollRef.current?.scrollToBottom();
  }, [messages.length, streamingText]);

  // Track terminal height for fixed layout + handle resize
  useEffect(() => {
    const onResize = () => {
      setTermHeight(stdout?.rows ?? 24);
      scrollRef.current?.remeasure();
    };
    stdout?.on("resize", onResize);
    return () => {
      stdout?.off("resize", onResize);
    };
  }, [stdout]);

  // Scroll keyboard handling (Up/Down arrows)
  useInput(
    (_input, key) => {
      if (key.upArrow) scrollRef.current?.scrollBy(-1);
      if (key.downArrow) scrollRef.current?.scrollBy(1);
    },
    { isActive: true },
  );

  return (
    <Box flexDirection="column" height={termHeight}>
      {/* StatusBar — pinned at top */}
      <Box flexShrink={0}>
        <StatusBar
          currentState={currentState}
          callId={callId}
          configSource={configSource}
          isStreaming={isStreaming}
          rewindMode={rewindMode}
        />
      </Box>

      {/* Scrollable message list — takes all remaining space */}
      <Box flexGrow={1} overflow="hidden" flexDirection="column">
        <ScrollView ref={scrollRef}>
          {messages.map((msg) => (
            <Box key={msg.id} flexDirection="column">
              <MessageBubble message={msg} />
              {msg.toolCalls && msg.toolCalls.length > 0 && (
                <ToolCallDisplay toolCalls={msg.toolCalls} />
              )}
            </Box>
          ))}

          {/* Live streaming text inside scroll area */}
          {isStreaming && !showContext && (
            <Box marginBottom={0}>
              <Text>
                <Text color={theme.primary} bold>
                  Assistant:
                </Text>{" "}
                <Text>{streamingText}</Text>
                <Text color={theme.primary}>|</Text>
              </Text>
            </Box>
          )}
        </ScrollView>
      </Box>

      {/* Context overlay — always mounted, toggled via display */}
      <Box display={showContext ? "flex" : "none"} flexDirection="column" flexShrink={0}>
        <ContextViewer
          dynamicVars={promptData?.dynamicVars ?? null}
          currentState={promptData?.state ?? currentState ?? null}
        />
      </Box>

      {/* Input — pinned at bottom */}
      <Box marginTop={0} flexShrink={0}>
        <InputBar
          onSubmit={onSendMessage}
          disabled={inputDisabled}
          focus={!inputDisabled}
          placeholder={isStreaming ? "Waiting for response..." : "Type a message..."}
          batchMode={batchMode}
          batchLines={batchLines}
          onBatchAdd={onBatchAdd}
          onBatchSend={onBatchSend}
        />
      </Box>

      {/* Keyboard hints — pinned at bottom */}
      <Box flexShrink={0}>
        <Text color={theme.muted} dimColor>
          Ctrl+E export  Ctrl+L logs  Ctrl+S save  Ctrl+R rewind  Ctrl+X context  Ctrl+P prompt  Ctrl+B batch  Ctrl+C exit
        </Text>
      </Box>
    </Box>
  );
}
