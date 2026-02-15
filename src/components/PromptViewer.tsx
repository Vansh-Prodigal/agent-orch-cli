import React from "react";
import { Box, Text } from "ink";
import { theme } from "../theme.js";

interface Props {
  prompt: string | null;
  state: string | null;
  dynamicVars: Record<string, unknown> | null;
}

export function PromptViewer({ prompt, state, dynamicVars }: Props) {
  return (
    <Box
      flexDirection="column"
      borderStyle="double"
      borderColor={theme.success}
      paddingX={1}
    >
      <Text color={theme.success} bold>
        Current Prompt [state: {state ?? "—"}] — press Escape to close
      </Text>
      <Text />

      {dynamicVars && Object.keys(dynamicVars).length > 0 && (
        <Box flexDirection="column" marginBottom={1}>
          <Text color={theme.warning} bold>
            Dynamic Variables:
          </Text>
          {Object.entries(dynamicVars).map(([key, value]) => (
            <Text key={key} color={theme.muted}>
              {key}: {truncate(formatValue(value), 200)}
            </Text>
          ))}
          <Text />
        </Box>
      )}

      <Text color={theme.emphasis} bold>
        Assembled Prompt:
      </Text>
      {prompt ? (
        <Text wrap="wrap">{prompt}</Text>
      ) : (
        <Text color={theme.muted} dimColor>Loading...</Text>
      )}
    </Box>
  );
}

function formatValue(v: unknown): string {
  if (typeof v === "string") return v;
  if (v === null || v === undefined) return "null";
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return s.slice(0, max) + "...";
}
