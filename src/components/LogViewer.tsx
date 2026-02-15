import React from "react";
import { Box, Text } from "ink";
import { theme } from "../theme.js";

interface Props {
  lines: string[];
  visible: boolean;
}

const DISPLAY_LINES = 20;

export function LogViewer({ lines, visible }: Props) {
  if (!visible) return null;

  const displayLines = lines.slice(-DISPLAY_LINES);

  return (
    <Box
      flexDirection="column"
      borderStyle="double"
      borderColor={theme.warning}
      paddingX={1}
      height={DISPLAY_LINES + 2}
    >
      <Text color={theme.warning} bold>
        Logs (last {displayLines.length} lines) — press Escape to close
      </Text>
      {displayLines.map((line, i) => (
        <Text key={i} color={theme.muted} dimColor wrap="truncate">
          {line}
        </Text>
      ))}
      {lines.length === 0 && (
        <Text color={theme.muted} dimColor>
          No logs yet.
        </Text>
      )}
    </Box>
  );
}
