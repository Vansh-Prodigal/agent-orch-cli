import React, { useCallback, useRef, useState } from "react";
import { Box, Text, useApp } from "ink";
import { useAgent } from "./hooks/useAgent.js";
import { useChat } from "./hooks/useChat.js";
import { useLogs } from "./hooks/useLogs.js";
import { useSession } from "./hooks/useSession.js";
import { useKeyboard } from "./hooks/useKeyboard.js";
import { SetupScreen } from "./components/SetupScreen.js";
import { ChatView } from "./components/ChatView.js";
import { LogViewer } from "./components/LogViewer.js";
import * as cmds from "./protocol/commands.js";
import type { BackendEvent, PromptEvent, ContextEvent } from "./protocol/types.js";
import { isReady } from "./protocol/events.js";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { deepMerge } from "./utils/deepMerge.js";
import { theme } from "./theme.js";

type Phase = "waiting" | "setup" | "chatting" | "ended";

/** Resolve the cli/ directory (where this package lives). */
function getCliDir(): string {
  // In ESM, import.meta.url gives us the file URL of this module.
  // Compiled output lives in cli/dist/, so cli/ is one level up.
  try {
    const thisFile = fileURLToPath(import.meta.url);
    // dist/App.js -> dist/ -> cli/
    return dirname(dirname(thisFile));
  } catch {
    // Fallback: process.cwd() should be cli/
    return process.cwd();
  }
}

const CLI_DIR = getCliDir();

/** Ensure an exports subdirectory exists, creating it if needed. */
function ensureExportsDir(subdir: string): string {
  const dir = join(CLI_DIR, "exports", subdir);
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }
  return dir;
}

export interface AppProps {
  toNumber?: string;
  fromNumber?: string;
  configPath?: string;
  configOverridePath?: string;
  loadSessionPath?: string;
  pythonPath?: string;
  projectRoot?: string;
  verbose?: boolean;
}

export function App({
  toNumber,
  fromNumber,
  configPath,
  configOverridePath,
  loadSessionPath,
  pythonPath,
  projectRoot,
  verbose = false,
}: AppProps) {
  const { exit } = useApp();
  const [phase, setPhase] = useState<Phase>("waiting");
  const [showLogs, setShowLogs] = useState(false);
  const [showContext, setShowContext] = useState(false);
  const [batchMode, setBatchMode] = useState(false);
  const [batchLines, setBatchLines] = useState<string[]>([]);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const configRef = useRef<Record<string, unknown>>({});

  // Pending export flags — when set, the next prompt/context event is
  // intercepted for file export instead of being passed to useChat.
  const pendingPromptExport = useRef(false);
  const pendingChatExport = useRef(false);

  const chat = useChat();
  const logs = useLogs();
  const session = useSession();

  const onEvent = useCallback(
    (event: BackendEvent) => {
      if (isReady(event)) {
        if (loadSessionPath) {
          // When resuming a session we should NOT enter the setup screen.
          // SetupScreen auto-submits when `--to-number`/`--config` are provided,
          // which would send a second load command (load_config/load_config_file)
          // and "restart" the conversation a few seconds after resume.
          setPhase("waiting");
          agent.sendCommand(
            cmds.loadSession(loadSessionPath, {
              configPath,
              toNumber,
              fromNumber,
            }),
          );
        } else {
          setPhase("setup");
        }
        return;
      }

      // --- Intercept prompt events for file export (Ctrl+P) ---
      if (event.event === "prompt" && pendingPromptExport.current) {
        pendingPromptExport.current = false;
        const pe = event as PromptEvent;
        try {
          const dir = ensureExportsDir("prompts");
          const ts = new Date().toISOString().replace(/[:.]/g, "-");
          const stateName = pe.state || "unknown";
          const filename = `prompt_${stateName}_${ts}.md`;
          const filePath = join(dir, filename);

          // Build dynamic variables section
          let dynamicVarsSection = "";
          if (pe.dynamic_vars && Object.keys(pe.dynamic_vars).length > 0) {
            dynamicVarsSection = "## Dynamic Variables\n";
            for (const [key, value] of Object.entries(pe.dynamic_vars)) {
              const display = typeof value === "string" ? value : JSON.stringify(value);
              dynamicVarsSection += `- **${key}**: ${display}\n`;
            }
            dynamicVarsSection += "\n";
          }

          const markdown = `# System Prompt — state: ${stateName}\nGenerated: ${new Date().toISOString()}\n\n${dynamicVarsSection}## Assembled Prompt\n${pe.prompt}\n`;

          writeFileSync(filePath, markdown, "utf-8");
          setStatusMessage(`Prompt exported to ${filePath}`);
        } catch (e) {
          setStatusMessage(`Prompt export failed: ${e}`);
        }
        setTimeout(() => setStatusMessage(null), 3000);
        return; // Don't pass to chat.handleEvent
      }

      // --- Intercept context events for chat export (Ctrl+E) ---
      if (event.event === "context" && pendingChatExport.current) {
        pendingChatExport.current = false;
        const ce = event as ContextEvent;
        try {
          const dir = ensureExportsDir("chats");
          const ts = new Date().toISOString().replace(/[:.]/g, "-");
          const id = chat.callId || "unknown";
          const filename = `chat_${id}_${ts}.json`;
          const filePath = join(dir, filename);

          // Add index to each message
          const indexedMessages = ce.messages.map((msg, i) => ({
            index: i,
            ...msg,
          }));

          const exportData = {
            version: "1.0.0",
            call_id: chat.callId,
            current_state: ce.current_state || chat.currentState,
            dynamic_vars: ce.dynamic_vars || {},
            resume_from: null as number | null,
            messages: indexedMessages,
            exported_at: new Date().toISOString(),
          };

          writeFileSync(filePath, JSON.stringify(exportData, null, 2), "utf-8");
          setStatusMessage(`Chat exported to ${filePath}`);
        } catch (e) {
          setStatusMessage(`Chat export failed: ${e}`);
        }
        setTimeout(() => setStatusMessage(null), 3000);
        return; // Don't pass to chat.handleEvent
      }

      chat.handleEvent(event);

      // Store config when loaded
      if (event.event === "config_loaded") {
        const cle = event as { config?: Record<string, unknown> };
        if (cle.config) {
          configRef.current = cle.config;
        }
        setPhase("chatting");
      }
      if (event.event === "call_ended") {
        setPhase("ended");
      }
    },
    [loadSessionPath],
  );

  const agent = useAgent({
    pythonPath,
    cwd: projectRoot,
    verbose,
    onEvent,
    onStderr: logs.addLine,
    onExit: (code) => {
      if (phase !== "ended") {
        setStatusMessage(`Backend exited with code ${code}`);
        setPhase("ended");
      }
    },
  });

  // --- Config loading handlers ---

  const handleLoadRemote = useCallback(
    (toNum: string, fromNum?: string) => {
      let overrides: Record<string, unknown> | undefined;
      if (configOverridePath) {
        try {
          overrides = JSON.parse(readFileSync(configOverridePath, "utf-8"));
        } catch (e) {
          setStatusMessage(`Failed to read override file: ${e}`);
        }
      }
      agent.sendCommand(
        cmds.loadConfig(toNum, {
          fromNumber: fromNum || fromNumber,
          configOverrides: overrides,
        }),
      );
    },
    [agent, fromNumber, configOverridePath],
  );

  const handleLoadFile = useCallback(
    (path: string) => {
      if (configOverridePath) {
        // Load both files and merge client-side, then send as config_file
        // Actually the backend handles overrides — but for local file + override
        // we'd need a different approach. For now just load the file.
      }
      agent.sendCommand(cmds.loadConfigFile(path));
    },
    [agent, configOverridePath],
  );

  // --- Message sending ---

  const handleSendMessage = useCallback(
    (text: string) => {
      chat.addUserMessage(text);
      agent.sendCommand(cmds.sendMessage(text));
    },
    [agent, chat],
  );

  // --- Batch mode ---

  const handleToggleBatch = useCallback(() => {
    setBatchMode((v) => !v);
    setBatchLines([]);
  }, []);

  const handleBatchAdd = useCallback((line: string) => {
    setBatchLines((prev) => [...prev, line]);
  }, []);

  const handleBatchSend = useCallback(() => {
    const lines = batchLines;
    setBatchLines([]);
    setBatchMode(false);
    for (const line of lines) {
      chat.addUserMessage(line);
      agent.sendCommand(cmds.sendMessage(line));
    }
  }, [batchLines, agent, chat]);

  // --- End call ---

  const handleEndCall = useCallback(() => {
    agent.sendCommand(cmds.endCall());
  }, [agent]);

  // --- Keyboard shortcuts ---

  const handleExport = useCallback(() => {
    // Ctrl+E: export chat in exact LLM format via getContext
    pendingChatExport.current = true;
    agent.sendCommand(cmds.getContext());
  }, [agent]);

  const handleSaveSession = useCallback(() => {
    const dir = ensureExportsDir("sessions");
    const ts = new Date().toISOString().replace(/[:.]/g, "-");
    const path = join(dir, `session_${ts}.json`);
    session.save(path, {
      callId: chat.callId,
      configSource: chat.configSource,
      config: configRef.current,
      messages: chat.messages,
      transcript: chat.finalTranscript || [],
      currentState: chat.currentState,
    });
    setStatusMessage(`Session saved to ${path}`);
    setTimeout(() => setStatusMessage(null), 3000);
  }, [chat, session]);

  // --- Context / Prompt viewers ---

  const handleShowContext = useCallback(() => {
    if (showContext) {
      setShowContext(false);
      chat.clearContext();
    } else {
      agent.sendCommand(cmds.getPrompt());
      setShowContext(true);
      setShowLogs(false);
    }
  }, [agent, showContext]);

  const handleExportPrompt = useCallback(() => {
    // Ctrl+P: export prompt to markdown file
    pendingPromptExport.current = true;
    agent.sendCommand(cmds.getPrompt());
  }, [agent]);

  useKeyboard({
    onExport: handleExport,
    onToggleLogs: () => {
      setShowLogs((v) => {
        if (!v) {
          setShowContext(false);
        }
        return !v;
      });
    },
    onSaveSession: handleSaveSession,
    onEndCall: handleEndCall,
    onEscape: () => {
      if (showLogs) setShowLogs(false);
      if (showContext) { setShowContext(false); chat.clearContext(); }
      if (batchMode) { setBatchMode(false); setBatchLines([]); }
    },
    onShowContext: handleShowContext,
    onShowPrompt: handleExportPrompt,
    onToggleBatch: handleToggleBatch,
    enabled: phase !== "waiting",
  });

  // --- Render ---

  // Always allow the log overlay, even during setup/loading.
  if (showLogs) {
    return (
      <Box flexDirection="column" flexGrow={1}>
        <LogViewer lines={logs.lines} visible />
        <Box>
          <Text color={theme.muted} dimColor>
            Escape close  |  Ctrl+L logs  Ctrl+C exit
          </Text>
        </Box>
      </Box>
    );
  }

  if (phase === "waiting") {
    return (
      <Box flexDirection="column" padding={1}>
<Text color={theme.primary} bold>
        ProAgent CLI
        </Text>
        <Text color={theme.muted}>Starting backend...</Text>
      </Box>
    );
  }

  if (phase === "setup") {
    return (
      <SetupScreen
        onLoadRemote={handleLoadRemote}
        onLoadFile={handleLoadFile}
        initialToNumber={toNumber}
        initialConfigPath={configPath}
        logs={logs.lines}
        verbose={verbose}
      />
    );
  }

  if (phase === "ended") {
    return (
      <Box flexDirection="column" padding={1}>
        <Text color={theme.primary} bold>
          ProAgent CLI — Call Ended
        </Text>
        {statusMessage && <Text color={theme.warning}>{statusMessage}</Text>}
        <Text>
          Messages exchanged: {chat.messages.length}
        </Text>
        <Text color={theme.muted}>
          Press Ctrl+E to export transcript, or Ctrl+C to exit.
        </Text>
        {chat.lastError && (
          <Text color={theme.error}>Last error: {chat.lastError}</Text>
        )}
      </Box>
    );
  }

  return (
    <Box flexDirection="column" flexGrow={1}>
      {chat.lastError && (
        <Box paddingX={1}>
          <Text color={theme.error} bold>
            Error: {chat.lastError}
          </Text>
        </Box>
      )}

      {statusMessage && (
        <Box paddingX={1}>
          <Text color={theme.success}>{statusMessage}</Text>
        </Box>
      )}

      <ChatView
        messages={chat.messages}
        streamingText={chat.streamingText}
        isStreaming={chat.isStreaming}
        currentState={chat.currentState}
        callId={chat.callId}
        configSource={chat.configSource}
        onSendMessage={handleSendMessage}
        inputDisabled={chat.isStreaming}
        batchMode={batchMode}
        batchLines={batchLines}
        onBatchAdd={handleBatchAdd}
        onBatchSend={handleBatchSend}
        showContext={showContext}
        promptData={chat.promptData}
      />
    </Box>
  );
}
