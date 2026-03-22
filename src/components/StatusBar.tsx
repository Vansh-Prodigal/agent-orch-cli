import React from "react";
import { Box, Text } from "ink";
import { theme, glyph } from "../theme.js";

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
      borderStyle="round"
      borderColor={rewindMode ? theme.warning : isStreaming ? theme.accent : theme.border}
      paddingX={1}
      width="100%"
    >
      <Text>
        <Text color={theme.primary} bold>
          {glyph.diamondD} PROAGENT
        </Text>
        <Text color={theme.border}> {glyph.sep} </Text>
        <Text color={theme.warning} bold>
          {glyph.arrow} {currentState || "—"}
        </Text>
        <Text color={theme.border}> {glyph.sep} </Text>
        <Text color={theme.muted}>
          call {glyph.dot} {callId || "—"}
        </Text>
        <Text color={theme.border}> {glyph.sep} </Text>
        <Text color={theme.muted}>
          cfg {glyph.dot} {configSource || "—"}
        </Text>
        {isStreaming && (
          <>
            <Text color={theme.border}> {glyph.sep} </Text>
            <Text color={theme.accent} bold>
              {glyph.gear} streaming
            </Text>
          </>
        )}
        {rewindMode && (
          <>
            <Text color={theme.border}> {glyph.sep} </Text>
            <Text color={theme.warning} bold>
              {glyph.arrow} REWIND
            </Text>
          </>
        )}
      </Text>
    </Box>
  );
}
