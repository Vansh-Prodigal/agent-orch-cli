import React from "react";
import { Box, Text } from "ink";
import type { ChatMessage } from "../protocol/types.js";
import { theme, glyph } from "../theme.js";

const ROLE_STYLES: Record<string, { color: string; icon: string; label: string }> = {
  user:      { color: theme.success, icon: glyph.bullet,   label: "You" },
  assistant: { color: theme.primary, icon: glyph.diamond,  label: "Assistant" },
  system:    { color: theme.warning, icon: glyph.arrow,    label: "System" },
};

interface Props {
  message: ChatMessage;
}

export function MessageBubble({ message }: Props) {
  const style = ROLE_STYLES[message.role] || {
    color: theme.emphasis,
    icon: glyph.dot,
    label: message.role,
  };

  // Skip rendering empty assistant messages (tool-call-only entries)
  if (!message.content && message.role === "assistant") {
    return <Box />;
  }

  return (
    <Box flexDirection="column" marginBottom={1}>
      <Text>
        <Text color={style.color} bold>
          {style.icon} {style.label}
        </Text>
      </Text>
      <Box marginLeft={2}>
        <Text wrap="wrap">{message.content}</Text>
      </Box>
    </Box>
  );
}
