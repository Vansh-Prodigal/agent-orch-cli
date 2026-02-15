import React from "react";
import { Box, Text } from "ink";
import type { ChatMessage } from "../protocol/types.js";
import { theme } from "../theme.js";

const ROLE_COLORS: Record<string, string> = {
  user: theme.success,
  assistant: theme.primary,
  system: theme.warning,
};

const ROLE_LABELS: Record<string, string> = {
  user: "You",
  assistant: "Assistant",
  system: "System",
};

interface Props {
  message: ChatMessage;
}

export function MessageBubble({ message }: Props) {
  const color = ROLE_COLORS[message.role] || "white";
  const label = ROLE_LABELS[message.role] || message.role;

  // Skip rendering empty assistant messages (tool-call-only entries)
  if (!message.content && message.role === "assistant") {
    return <Box />;
  }

  return (
    <Box flexDirection="column" marginBottom={1}>
      <Text wrap="wrap">
        <Text color={color} bold>
          {label}:
        </Text>{" "}
        <Text>{message.content}</Text>
      </Text>
    </Box>
  );
}
