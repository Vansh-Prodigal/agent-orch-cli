import React, { useCallback, useEffect, useRef } from "react";
import { Box, Text, useInput, useStdout } from "ink";
import { useMouseScroll } from "../hooks/useMouseScroll.js";
import { ScrollView } from "ink-scroll-view";
import type { ScrollViewRef } from "ink-scroll-view";
import { theme, glyph } from "../theme.js";
import { logColor } from "../utils/logColor.js";

interface Props {
  lines: string[];
  visible: boolean;
  mouseMode?: boolean;
  onDump?: () => void;
}

export function LogViewer({ lines, visible, mouseMode = true, onDump }: Props) {
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
  useInput((input, key) => {
    if (key.upArrow) scrollRef.current?.scrollBy(-1);
    if (key.downArrow) scrollRef.current?.scrollBy(1);
    if (input === "s" && onDump) onDump();
  });

  // Mouse wheel scrolling
  const handleMouseScroll = useCallback(
    (delta: number) => scrollRef.current?.scrollBy(delta),
    [],
  );
  useMouseScroll(handleMouseScroll, mouseMode);

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
            {" "}({lines.length} lines) {glyph.dot} {"\u2191\u2193"} scroll {glyph.dot} s dump {glyph.dot} Escape to close
          </Text>
        </Text>
      </Box>
      <Box flexGrow={1} overflow="hidden" flexDirection="column">
        <ScrollView ref={scrollRef}>
          {lines.map((line, i) => (
            <Text key={i} color={logColor(line)} wrap="wrap">
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
