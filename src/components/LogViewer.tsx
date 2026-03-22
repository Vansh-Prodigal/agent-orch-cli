import React, { useEffect, useRef } from "react";
import { Box, Text, useInput, useStdout } from "ink";
import { ScrollView } from "ink-scroll-view";
import type { ScrollViewRef } from "ink-scroll-view";
import { theme, glyph } from "../theme.js";

interface Props {
  lines: string[];
  visible: boolean;
}

export function LogViewer({ lines, visible }: Props) {
  if (!visible) return null;

  const scrollRef = useRef<ScrollViewRef>(null);
  const { stdout } = useStdout();

  // Auto-scroll to bottom when new lines arrive
  useEffect(() => {
    scrollRef.current?.scrollToBottom();
  }, [lines.length]);

  // Handle terminal resize
  useEffect(() => {
    const onResize = () => scrollRef.current?.remeasure();
    stdout?.on("resize", onResize);
    return () => {
      stdout?.off("resize", onResize);
    };
  }, [stdout]);

  // Scroll keyboard handling
  useInput((_input, key) => {
    if (key.upArrow) scrollRef.current?.scrollBy(-1);
    if (key.downArrow) scrollRef.current?.scrollBy(1);
  });

  return (
    <Box
      flexDirection="column"
      borderStyle="single"
      borderColor={theme.warning}
      paddingX={1}
      flexGrow={1}
    >
      <Box flexShrink={0}>
        <Text color={theme.warning} bold>
          {glyph.diamondD} Logs
          <Text color={theme.muted}>
            {" "}({lines.length} lines) {glyph.dot} {"\u2191\u2193"} scroll {glyph.dot} Escape to close
          </Text>
        </Text>
      </Box>
      <Box flexGrow={1} overflow="hidden" flexDirection="column">
        <ScrollView ref={scrollRef}>
          {lines.map((line, i) => (
            <Text key={i} color={theme.muted} dimColor wrap="truncate">
              {line}
            </Text>
          ))}
          {lines.length === 0 && (
            <Text color={theme.muted}>
              No logs yet.
            </Text>
          )}
        </ScrollView>
      </Box>
    </Box>
  );
}
