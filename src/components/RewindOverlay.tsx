import React, { useEffect, useRef, useState } from "react";
import { Box, Text, useInput, useStdout } from "ink";
import TextInput from "ink-text-input";
import { ScrollView } from "ink-scroll-view";
import type { ScrollViewRef } from "ink-scroll-view";
import type { ChatMessage, ToolCallInfo } from "../protocol/types.js";
import { theme, glyph } from "../theme.js";
import { MessageBubble } from "./MessageBubble.js";
import { ToolCallDisplay } from "./ToolCallDisplay.js";

export interface RewindItem {
  displayIndex: number;
  transcriptIndex: number;
  message: ChatMessage;
}

interface Props {
  items: RewindItem[];
  onSelect: (transcriptIndex: number) => void;
  onCancel: () => void;
}

export function RewindOverlay({ items, onSelect, onCancel }: Props) {
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<ScrollViewRef>(null);
  const { stdout } = useStdout();

  const maxIndex = items.length;

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
    if (key.escape) onCancel();
  });

  const handleSubmit = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    const displayIndex = parseInt(trimmed, 10);
    if (isNaN(displayIndex) || displayIndex < 1 || displayIndex > maxIndex) {
      setError(`Invalid. Enter a number between 1 and ${maxIndex}`);
      return;
    }
    setError(null);
    const target = items[displayIndex - 1];
    onSelect(target.transcriptIndex);
  };

  return (
    <Box flexDirection="column" flexGrow={1}>
      <Box borderStyle="round" borderColor={theme.warning} paddingX={1}>
        <Text color={theme.warning} bold>
          {glyph.arrow} REWIND
        </Text>
        <Text color={theme.muted}>
          {"  "}Select a message to rewind to (1–{maxIndex})
        </Text>
      </Box>

      {/* Scrollable message list — same style as ChatView */}
      <Box flexGrow={1} overflow="hidden" flexDirection="column">
        <ScrollView ref={scrollRef}>
          {items.map((item) => (
            <Box key={item.message.id} flexDirection="row">
              {/* Index badge on the left */}
              <Box width={6} flexShrink={0} justifyContent="flex-end" marginRight={1}>
                <Text color={theme.warning} bold>
                  {item.displayIndex}
                </Text>
              </Box>
              {/* Actual message content */}
              <Box flexDirection="column" flexGrow={1}>
                <MessageBubble message={item.message} />
                {item.message.toolCalls && item.message.toolCalls.length > 0 && (
                  <ToolCallDisplay toolCalls={item.message.toolCalls} />
                )}
              </Box>
            </Box>
          ))}
        </ScrollView>
      </Box>

      {/* Error message */}
      {error && (
        <Box>
          <Text color={theme.error}>{glyph.cross} {error}</Text>
        </Box>
      )}

      {/* Input */}
      <Box>
        <Text color={theme.warning} bold>
          R{glyph.prompt}{" "}
        </Text>
        <TextInput
          value={value}
          onChange={(v) => {
            setValue(v.replace(/[^0-9]/g, ""));
            setError(null);
          }}
          onSubmit={handleSubmit}
          focus={true}
          placeholder="Enter message number to rewind to..."
        />
      </Box>

      <Box>
        <Text color={theme.muted} dimColor>
          {glyph.bulletO} Esc cancel {glyph.dot} {"\u2191\u2193"} scroll {glyph.dot} Enter rewind
        </Text>
      </Box>
    </Box>
  );
}
