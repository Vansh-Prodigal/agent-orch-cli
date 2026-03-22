import React from "react";
import { Box, Text } from "ink";
import { theme, glyph } from "../theme.js";

interface Props {
  dynamicVars: Record<string, unknown> | null;
  currentState: string | null;
}

export function ContextViewer({ dynamicVars, currentState }: Props) {
  const entries = dynamicVars ? Object.entries(dynamicVars) : [];

  return (
    <Box
      flexDirection="column"
      borderStyle="single"
      borderColor={theme.info}
      paddingX={1}
    >
      <Text color={theme.info} bold>
        {glyph.diamondD} Dynamic Variables
        <Text color={theme.muted}>
          {" "}[{currentState || "—"}] {glyph.dot} Escape to close
        </Text>
      </Text>
      <Text />
      {entries.length === 0 ? (
        <Text color={theme.muted}>
          {dynamicVars ? "No dynamic variables set." : `${glyph.gear} Loading${glyph.ellipsis}`}
        </Text>
      ) : (
        entries.map(([key, value]) => (
          <Box key={key} flexDirection="column" marginBottom={0}>
            <Text>
              <Text color={theme.info} bold>
                {glyph.arrow} {key}
              </Text>{" "}
              <Text wrap="wrap">{formatValue(value)}</Text>
            </Text>
          </Box>
        ))
      )}
    </Box>
  );
}

function formatValue(v: unknown): string {
  if (typeof v === "string") return v;
  if (v === null || v === undefined) return "null";
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}
