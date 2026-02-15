import React from "react";
import { Box, Text } from "ink";
import { theme } from "../theme.js";

interface Props {
  currentState: string;
  callId: string;
  configSource: string;
  isStreaming: boolean;
}

export function StatusBar({
  currentState,
  callId,
  configSource,
  isStreaming,
}: Props) {
  return (
    <Box borderStyle="single" borderColor={theme.muted} paddingX={1}>
      <Text>
        <Text color={theme.warning} dimColor>
          [state: {currentState || "—"}]
        </Text>
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
      </Text>
    </Box>
  );
}
