import React from "react";
import { Box, Text } from "ink";
import type { ToolCallInfo } from "../protocol/types.js";
import { theme, glyph } from "../theme.js";

/** Tool names that get highlighted in warning/yellow. */
const HIGHLIGHT_TOOLS = new Set([
  "transfer_call",
  "end_the_call",
  "execute_code",
]);

const TRANSITION_PREFIX = "transition_to_";

interface Props {
  toolCalls: ToolCallInfo[];
  builtinStates?: Set<string>;
}

export function ToolCallDisplay({ toolCalls, builtinStates }: Props) {
  if (!toolCalls.length) return null;

  return (
    <Box flexDirection="column" marginLeft={2} marginBottom={0}>
      {toolCalls.map((tc) => {
        const isTransition = tc.name.startsWith(TRANSITION_PREFIX);
        const dest = isTransition ? tc.name.slice(TRANSITION_PREFIX.length) : "";
        const isBuiltinTransition =
          isTransition && !!builtinStates && builtinStates.has(dest);
        const color = HIGHLIGHT_TOOLS.has(tc.name)
          ? theme.warning
          : isBuiltinTransition
            ? theme.builtin
            : theme.accent;
        return (
          <Box
            key={tc.tool_call_id}
            flexDirection="column"
            borderStyle="round"
            borderColor={color}
            paddingX={1}
          >
            <Text>
              <Text color={color} bold>
                {glyph.star} {tc.name}
              </Text>
              {isBuiltinTransition && (
                <Text color={color} dimColor>
                  {" "}
                  [type: builtin]
                </Text>
              )}
            </Text>
            {tc.arguments && (
              <Text color={theme.muted}>
                <Text color={color} dimColor>args</Text>{" "}
                {formatJson(tc.arguments)}
              </Text>
            )}
            {tc.result && (
              <Text color={theme.muted}>
                <Text color={color} dimColor>out </Text>{" "}
                {truncate(tc.result, 200)}
              </Text>
            )}
          </Box>
        );
      })}
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
  return s.slice(0, max) + glyph.ellipsis;
}
