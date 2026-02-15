import React from "react";
import { Box, Static, Text } from "ink";
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
}: Props) {
  return (
    <Box flexDirection="column" flexGrow={1}>
      <StatusBar
        currentState={currentState}
        callId={callId}
        configSource={configSource}
        isStreaming={isStreaming}
      />

      {/* Permanent scrollback — always rendered */}
      <Static items={messages}>
        {(msg) => (
          <Box key={msg.id} flexDirection="column">
            <MessageBubble message={msg} />
            {msg.toolCalls && msg.toolCalls.length > 0 && (
              <ToolCallDisplay toolCalls={msg.toolCalls} />
            )}
          </Box>
        )}
      </Static>

      {/* Context overlay — always mounted, toggled via display */}
      <Box display={showContext ? "flex" : "none"} flexDirection="column">
        <ContextViewer
          dynamicVars={promptData?.dynamicVars ?? null}
          currentState={promptData?.state ?? currentState ?? null}
        />
      </Box>

      {/* Live streaming region — hidden when overlay active */}
      {isStreaming && (
        <Box display={showContext ? "none" : "flex"} marginBottom={0}>
          <Text>
<Text color={theme.primary} bold>
            Assistant:
            </Text>{" "}
            <Text>{streamingText}</Text>
            <Text color={theme.primary}>|</Text>
          </Text>
        </Box>
      )}

      {/* Input — always visible */}
      <Box marginTop={0}>
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

      {/* Keyboard hints */}
      <Box>
        <Text color={theme.muted} dimColor>
          Ctrl+E export  Ctrl+L logs  Ctrl+S save  Ctrl+X context  Ctrl+P prompt  Ctrl+B batch  Ctrl+C exit
        </Text>
      </Box>
    </Box>
  );
}
