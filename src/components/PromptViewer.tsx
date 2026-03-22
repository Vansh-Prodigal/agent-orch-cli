import React from "react";
import { Box, Text } from "ink";
import { theme, glyph } from "../theme.js";

interface Props {
  prompt: string | null;
  state: string | null;
  dynamicVars: Record<string, unknown> | null;
}

export function PromptViewer({ prompt, state, dynamicVars }: Props) {
  return (
    <Box
      flexDirection="column"
      borderStyle="single"
      borderColor={theme.success}
      paddingX={1}
    >
      <Text color={theme.success} bold>
        {glyph.diamondD} Prompt
        <Text color={theme.muted}>
          {" "}[{state ?? "—"}] {glyph.dot} Escape to close
        </Text>
      </Text>
      <Text />

      {dynamicVars && Object.keys(dynamicVars).length > 0 && (
        <Box flexDirection="column" marginBottom={1}>
          <Text color={theme.warning} bold>
            {glyph.arrow} Dynamic Variables
          </Text>
          {Object.entries(dynamicVars).map(([key, value]) => (
            <Text key={key} color={theme.muted}>
              {"  "}{glyph.bulletO} {key}: {truncate(formatValue(value), 200)}
            </Text>
          ))}
          <Text />
        </Box>
      )}

      <Text color={theme.emphasis} bold>
        {glyph.arrow} Assembled Prompt
      </Text>
      {prompt ? (
        <Text wrap="wrap">{prompt}</Text>
      ) : (
        <Text color={theme.muted}>
          {glyph.gear} Loading{glyph.ellipsis}
        </Text>
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
  return s.slice(0, max) + glyph.ellipsis;
}
