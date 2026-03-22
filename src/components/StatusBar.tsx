import React from "react";
import { Box, Text } from "ink";
import { theme } from "../theme.js";

interface Props {
  currentState: string;
  callId: string;
  configSource: string;
  isStreaming: boolean;
  rewindMode?: boolean;
}

export function StatusBar({
  currentState,
  callId,
  configSource,
  isStreaming,
  rewindMode,
}: Props) {
  return (
    <Box
      borderStyle="single"
      borderColor={theme.muted}
      paddingX={1}
      width="100%"
    >
      <Text>
        <Text color={theme.warning}>[state: {currentState || "—"}]</Text>
        {"  "}
        <Text color={theme.muted} dimColor>
          [call_id: {callId || "—"}]
        </Text>
        {"  "}
        <Text color={theme.muted} dimColor>
          [config: {configSource || "—"}]
        </Text>
        {isStreaming && (
          <>
            {"  "}
            <Text color={theme.primary} dimColor>
              [streaming...]
            </Text>
          </>
        )}
        {rewindMode && (
          <>
            {"  "}
            <Text color={theme.warning} bold>
              [REWIND]
            </Text>
          </>
        )}
      </Text>
    </Box>
  );
}
