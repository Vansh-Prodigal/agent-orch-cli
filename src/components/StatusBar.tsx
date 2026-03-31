import React from "react";
import { Box, Text } from "ink";
import { theme, glyph } from "../theme.js";

interface Props {
  currentState: string;
  callId: string;
  configSource: string;
  isStreaming: boolean;
  rewindMode?: boolean;
  autopilotProgress?: string | null;
  dynamicPromptIndex?: number | null;
  dynamicPromptCondition?: string | null;
}

export function StatusBar({
  currentState,
  callId,
  configSource,
  isStreaming,
  rewindMode,
  autopilotProgress,
  dynamicPromptIndex,
  dynamicPromptCondition,
}: Props) {
  return (
    <Box
      borderStyle="round"
      borderColor={autopilotProgress ? theme.info : rewindMode ? theme.warning : isStreaming ? theme.accent : theme.border}
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
        {dynamicPromptIndex != null && (
          <>
            <Text color={theme.border}> {glyph.sep} </Text>
            <Text color={theme.info} bold>
              dp:{dynamicPromptIndex}
            </Text>
            {dynamicPromptCondition && (
              <Text color={theme.muted}>
                {" "}{dynamicPromptCondition}
              </Text>
            )}
          </>
        )}
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
        {autopilotProgress && (
          <>
            <Text color={theme.border}> {glyph.sep} </Text>
            <Text color={theme.info} bold>
              {glyph.gear} AUTOPILOT [{autopilotProgress}]
            </Text>
          </>
        )}
      </Text>
    </Box>
  );
}
