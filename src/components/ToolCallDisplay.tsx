import React from "react";
import { Box, Text } from "ink";
import type { ToolCallInfo } from "../protocol/types.js";
import { theme } from "../theme.js";

interface Props {
  toolCalls: ToolCallInfo[];
}

export function ToolCallDisplay({ toolCalls }: Props) {
  if (!toolCalls.length) return null;

  return (
    <Box flexDirection="column" marginLeft={2} marginBottom={0}>
      {toolCalls.map((tc) => (
        <Box
          key={tc.tool_call_id}
          flexDirection="column"
          borderStyle="round"
          borderColor={theme.accent}
          paddingX={1}
        >
          <Text color={theme.accent} bold>
            [tool] {tc.name}
          </Text>
          {tc.arguments && (
            <Text color={theme.muted}>
              args: {formatJson(tc.arguments)}
            </Text>
          )}
          {tc.result && (
            <Text color={theme.muted}>
              result: {truncate(tc.result, 200)}
            </Text>
          )}
        </Box>
      ))}
    </Box>
  );
}

function formatJson(s: string): string {
  try {
    const parsed = JSON.parse(s);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return s;
  }
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return s.slice(0, max) + "...";
}
