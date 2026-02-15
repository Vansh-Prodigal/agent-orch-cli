import React from "react";
import { Box, Text } from "ink";
import { theme } from "../theme.js";

interface Props {
  dynamicVars: Record<string, unknown> | null;
  currentState: string | null;
}

export function ContextViewer({ dynamicVars, currentState }: Props) {
  const entries = dynamicVars ? Object.entries(dynamicVars) : [];

  return (
    <Box
      flexDirection="column"
      borderStyle="double"
      borderColor={theme.info}
      paddingX={1}
    >
      <Text color={theme.info} bold>
        Dynamic Variables [state: {currentState || "—"}] — press Escape to close
      </Text>
      <Text />
      {entries.length === 0 ? (
        <Text color={theme.muted} dimColor>
          {dynamicVars ? "No dynamic variables set." : "Loading..."}
        </Text>
      ) : (
        entries.map(([key, value]) => (
          <Box key={key} flexDirection="column" marginBottom={0}>
            <Text>
              <Text color={theme.primary} bold>
                {key}:
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
