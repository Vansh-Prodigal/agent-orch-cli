import React, { useState } from "react";
import { Box, Text } from "ink";
import TextInput from "ink-text-input";
import { theme } from "../theme.js";
import { digitsToWords } from "../utils/digitsToWords.js";

interface Props {
  onSubmit: (text: string) => void;
  disabled: boolean;
  placeholder?: string;
  batchMode: boolean;
  batchLines: string[];
  onBatchAdd: (line: string) => void;
  onBatchSend: () => void;
  focus?: boolean;
}

export function InputBar({
  onSubmit,
  disabled,
  placeholder = "Type a message...",
  batchMode,
  batchLines,
  onBatchAdd,
  onBatchSend,
  focus = true,
}: Props) {
  const [value, setValue] = useState("");

  const handleChange = (val: string) => {
    // Strip control characters that may leak from ctrl+key shortcuts
    setValue(val.replace(/[\x00-\x1f]/g, ""));
  };

  const handleSubmit = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) {
      if (batchMode && batchLines.length > 0) {
        // Empty submit in batch mode = send the batch
        onBatchSend();
      }
      return;
    }
    const converted = digitsToWords(trimmed);
    if (batchMode) {
      onBatchAdd(converted);
    } else {
      onSubmit(converted);
    }
    setValue("");
  };

  if (disabled) {
    return (
      <Box>
        <Text color={theme.muted} dimColor>
          {placeholder}
        </Text>
      </Box>
    );
  }

  return (
    <Box flexDirection="column">
      {batchMode && batchLines.length > 0 && (
        <Box flexDirection="column" marginBottom={0}>
          <Text color={theme.warning} dimColor>
            Batch queue ({batchLines.length} messages, press Enter on empty line to send):
          </Text>
          {batchLines.map((line, i) => (
            <Text key={i} color={theme.muted}>
              {"  "}{i + 1}. {line}
            </Text>
          ))}
        </Box>
      )}
      <Box>
        <Text color={batchMode ? theme.warning : theme.success} bold>
          {batchMode ? "B>" : ">"}{" "}
        </Text>
        <TextInput
          value={value}
          onChange={handleChange}
          onSubmit={handleSubmit}
          focus={focus}
          placeholder={
            batchMode
              ? "Add message (Enter=add, empty Enter=send all)"
              : placeholder
          }
        />
      </Box>
    </Box>
  );
}
