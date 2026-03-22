import React, { useState } from "react";
import { Box, Text } from "ink";
import TextInput from "ink-text-input";
import { theme, glyph } from "../theme.js";

type ConfigMode = "select" | "remote" | "local";

interface Props {
  onLoadRemote: (toNumber: string, fromNumber?: string) => void;
  onLoadFile: (path: string) => void;
  initialToNumber?: string;
  initialConfigPath?: string;
  logs?: string[];
  verbose?: boolean;
}

/** Spaced-out banner title. */
function Banner() {
  return (
    <Box
      borderStyle="single"
      borderColor={theme.primary}
      paddingX={3}
      justifyContent="center"
      marginBottom={1}
    >
      <Text color={theme.primary} bold>
        {glyph.diamondD}{"  "}P R O A G E N T{"  "}C L I
      </Text>
    </Box>
  );
}

export function SetupScreen({
  onLoadRemote,
  onLoadFile,
  initialToNumber,
  initialConfigPath,
  logs = [],
  verbose = false,
}: Props) {
  const [mode, setMode] = useState<ConfigMode>(
    initialToNumber
      ? "remote"
      : initialConfigPath
        ? "local"
        : "select",
  );
  const [toNumber, setToNumber] = useState(initialToNumber || "");
  const [filePath, setFilePath] = useState(initialConfigPath || "");

  // Auto-submit if we got CLI args
  React.useEffect(() => {
    if (initialToNumber) {
      onLoadRemote(initialToNumber);
    } else if (initialConfigPath) {
      onLoadFile(initialConfigPath);
    }
  }, []);

  if (initialToNumber || initialConfigPath) {
    const displayLines = verbose ? logs.slice(-12) : [];
    return (
      <Box flexDirection="column" padding={1}>
        <Banner />
        <Text color={theme.muted}>
          {glyph.gear} Loading configuration{glyph.ellipsis}
        </Text>
        <Text color={theme.muted} dimColor>
          Press Ctrl+L to view backend logs.
        </Text>
        {verbose && (
          <>
            <Text />
            <Text color={theme.muted} dimColor>
              Verbose mode {glyph.dot} showing backend logs (tail)
            </Text>
            {displayLines.length > 0 ? (
              displayLines.map((line, i) => (
                <Text key={i} color={theme.muted} dimColor wrap="truncate">
                  {line}
                </Text>
              ))
            ) : (
              <Text color={theme.muted} dimColor>
                No logs yet. Press Ctrl+L for full log viewer.
              </Text>
            )}
          </>
        )}
      </Box>
    );
  }

  if (mode === "select") {
    return (
      <Box flexDirection="column" padding={1}>
        <Banner />
        <Text color={theme.emphasis}>How would you like to load the agent config?</Text>
        <Text />
        <Text>
          <Text color={theme.success} bold>[1]</Text>
          <Text color={theme.success}> {glyph.arrow} Remote — fetch by phone number</Text>
        </Text>
        <Text>
          <Text color={theme.warning} bold>[2]</Text>
          <Text color={theme.warning}> {glyph.arrow} Local  — load from JSON config file</Text>
        </Text>
        <Text />
        <SelectInput onSelect={(choice: string) => {
          if (choice === "1") setMode("remote");
          else if (choice === "2") setMode("local");
        }} />
      </Box>
    );
  }

  if (mode === "remote") {
    return (
      <Box flexDirection="column" padding={1}>
        <Banner />
        <Text color={theme.emphasis}>
          Enter the to_number (phone number to look up config for):
        </Text>
        <Box>
          <Text color={theme.success} bold>
            {glyph.prompt}{" "}
          </Text>
          <TextInput
            value={toNumber}
            onChange={setToNumber}
            onSubmit={(val) => {
              if (val.trim()) onLoadRemote(val.trim());
            }}
            placeholder="+1234567890"
          />
        </Box>
      </Box>
    );
  }

  // mode === "local"
  return (
    <Box flexDirection="column" padding={1}>
      <Banner />
      <Text color={theme.emphasis}>Enter path to config JSON file:</Text>
      <Box>
        <Text color={theme.warning} bold>
          {glyph.prompt}{" "}
        </Text>
        <TextInput
          value={filePath}
          onChange={setFilePath}
          onSubmit={(val) => {
            if (val.trim()) onLoadFile(val.trim());
          }}
          placeholder="simulator/chat_config.json"
        />
      </Box>
    </Box>
  );
}

/**
 * Simple 1/2 selection input.
 */
function SelectInput({ onSelect }: { onSelect: (choice: string) => void }) {
  const [value, setValue] = useState("");
  return (
    <Box>
      <Text color={theme.primary} bold>
        {glyph.prompt}{" "}
      </Text>
      <TextInput
        value={value}
        onChange={setValue}
        onSubmit={(val) => {
          if (val === "1" || val === "2") onSelect(val);
        }}
        placeholder="1 or 2"
      />
    </Box>
  );
}
