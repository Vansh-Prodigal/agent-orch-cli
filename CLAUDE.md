# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Interactive terminal UI for the ProAgent voice agent platform. A **TypeScript Ink (React) frontend** spawns a **Python backend** (`backend.py`) and they communicate via **JSON-lines over stdin/stdout**.

## Build & Dev Commands

```bash
npm run build        # TypeScript → dist/
npm run dev          # Watch mode (rebuilds on save)
npm run typecheck    # Type-check without emitting
npm start -- --config path/to/config.json   # Run after building
```

No test suite exists yet. No linter is configured.

## Architecture

### Two-Process Design

1. **TypeScript frontend** (`src/`) — Ink/React terminal UI, manages user interaction
2. **Python backend** (`backend.py`) — Loads configs, runs ProAgent state machine, streams LLM responses

The frontend spawns the Python process via `useAgent.ts` hook and communicates through JSON-line protocol:
- **Commands** (frontend → backend stdin): `load_config`, `send_message`, `get_context`, `get_prompt`, `rewind`, `end_call`, etc.
- **Events** (backend stdout → frontend): `config_loaded`, `stream_start`, `stream_chunk`, `stream_end`, `tool_calls`, `state_changed`, `rewind_complete`, `error`, etc.

Full type definitions are in `src/protocol/types.ts`.

### Frontend Hook Architecture

- `useAgent.ts` — Spawns Python subprocess, sends JSON commands, parses JSON events from stdout
- `useChat.ts` — Chat message state, streaming buffer, event-to-state mapping
- `useSession.ts` — Session save/load and chat export logic
- `useKeyboard.ts` — Global keyboard shortcuts (Ctrl+E/S/X/P/L/B/R)
- `useLogs.ts` — Collects backend stderr for log viewer

### App Lifecycle

`index.tsx` (meow CLI parsing) → `App.tsx` (phase state machine: waiting → setup → chatting → ended) → `ChatView.tsx` (message display + input)

### Backend Key Points

- All Python `print()`/logging goes to **stderr** — stdout is reserved for JSON events
- `backend.py` uses `state.chat_ctx` (livekit `ChatContext`) as the persistent conversation state across `agent.run()` calls
- After state transitions with `continue_after_transition=True`, a reconciliation step (`_reconcile_chat_ctx`) ensures post-transition text is added to the chat context
- Config can be loaded remotely (by phone number) or from local JSON files
- Session resume supports two formats: self-contained session files (Ctrl+S) and config-agnostic chat exports (Ctrl+E)

## Protocol Conventions

- Backend must **never** write non-JSON to stdout (breaks protocol parsing)
- Frontend renders messages using `ink-scroll-view`'s `<ScrollView>` component (supports dynamic add/remove for rewind)
- Each `stream_start`/`stream_end` pair corresponds to one LLM call's text output; `LLMUsage` chunks mark boundaries

## Rewind Support

The CLI supports rewinding conversations to a previous message (Ctrl+R):

- **Backend**: `handle_rewind` recreates the ProAgent from scratch via `_build_agent()` to ensure all internal state (state loops, PII stages, etc.) is fresh. State history is tracked in `state_timeline` and reconstructed from `transition_to_*` tool calls when loading sessions via `_rebuild_state_timeline_from_transcript()`.
- **Frontend**: `RewindOverlay` displays messages using the actual chat components (MessageBubble + ToolCallDisplay) with selectable 1-based indices. Only user/assistant messages are selectable; tool calls are included when their parent assistant message is selected.
- **Protocol**: `rewind` command sends a transcript index; `rewind_complete` event returns truncated `loaded_messages`, `current_state`, and `dynamic_vars`.

## Prodigal Technologies PR Standards

PRs follow a standard template with: Description, Justification, Type (Emergency/Standard), Impact Assessment, Rollback Procedure, Testing, Security (OWASP Top 10), and Checklist sections.
