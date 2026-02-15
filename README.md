# ProAgent CLI

Interactive terminal UI for simulating ProAgent conversations. This package renders an Ink (React) TUI and spawns a Python backend (`cli/backend.py`) that runs the actual ProAgent state machine and streams assistant output back to the UI.

## What this is for

- **Run a config locally** (remote by phone number or local JSON config file).
- **Replay/resume a conversation** from an exported transcript/session file.
- **Inspect prompts/context** and export them for debugging.

## Prerequisites

- **Node.js** (for the Ink UI)
- **Python** environment with this repo’s Python dependencies installed (the CLI backend imports `agent_orchestrator/` code)

If you haven’t set up Python deps yet, follow the repo root setup in `../README.md` (CodeArtifact login may be required) and install:

```bash
pip install -r requirements.txt
```

## Install (Node)

From `cli/`:

```bash
npm install
```

## Build & run

From `cli/`:

```bash
npm run build
node dist/index.js --help
```

## Usage

The CLI accepts these flags (see `cli/src/index.tsx`):

```bash
node dist/index.js [options]

# Options
#   --to-number, -t      Phone number to look up remote config
#   --from-number, -f    Caller phone number (default: +10000000000)
#   --config, -c         Path to local config JSON file
#   --override, -o       Path to config override JSON (merged on top)
#   --load-session, -l   Path to a saved session or chat export to resume
#   --python, -p         Path to Python interpreter
#   --project-root       Path to project root (default: auto-detect)
```

### Examples

Load remote config (by phone number):

```bash
node dist/index.js --to-number +12025551234
```

Load local config file:

```bash
node dist/index.js --config simulator/chat_config.json
```

Load remote config + JSON overrides:

```bash
node dist/index.js --to-number +12025551234 --override my_overrides.json
```

Resume from a saved session (self-contained):

```bash
node dist/index.js --load-session exports/sessions/session_2026-02-15T00-00-00.json
```

Resume from a chat export (config-agnostic; provide a config):

```bash
node dist/index.js --load-session exports/chats/chat_*.json --config simulator/chat_config.json
# or:
node dist/index.js --load-session exports/chats/chat_*.json --to-number +12025551234
```

## Resuming: file formats

`--load-session` supports **two** shapes (detected automatically by the backend):

- **Session file** (created by **Ctrl+S**)
  - Contains embedded `config`, `transcript`, `currentState`, `callId`, etc.
  - Intended to fully resume without needing external config.
- **Chat export** (created by **Ctrl+E**)
  - Contains `messages` in OpenAI-style format plus `current_state`, `dynamic_vars`, and optional `resume_from`.
  - Requires a config via `--config` or `--to-number`.

### `resume_from`

If `resume_from` is set to an integer, the backend slices the transcript to `[:resume_from + 1]` and then generates the **next** assistant continuation from that point.

## Keyboard shortcuts

While chatting:

- **Ctrl+E**: export full chat context (OpenAI-format JSON) to `cli/exports/chats/`
- **Ctrl+S**: save a resumeable session JSON to `cli/exports/sessions/`
- **Ctrl+X**: show context/prompt overlay
- **Ctrl+P**: export assembled prompt markdown to `cli/exports/prompts/`
- **Ctrl+L**: toggle log viewer
- **Ctrl+B**: batch input mode
- **Ctrl+C**: exit

Exports live under `cli/exports/` and are ignored by git (`cli/.gitignore`).

## How it works (for contributors)

- **UI**: TypeScript Ink app (`cli/src/`)
- **Backend**: Python process (`cli/backend.py`)
- **Protocol**: JSON-lines over stdin/stdout
  - UI sends commands like `load_config`, `load_config_file`, `load_session`, `send_message`
  - Backend emits events like `config_loaded`, `stream_start`, `stream_chunk`, `stream_end`, `tool_calls`, `state_changed`

Key code:

- `cli/src/hooks/useAgent.ts`: spawns Python backend and parses JSON-line events
- `cli/src/App.tsx`: top-level wiring + exports/saves
- `cli/backend.py`: config/session loading + ProAgent execution loop

## Troubleshooting

### Backend fails with missing Python modules

If you see errors like `ModuleNotFoundError: No module named 'livekit'`, your active Python interpreter doesn’t have the repo’s Python deps installed.

Fix:

- Activate the correct venv, then `pip install -r requirements.txt`
- Or pass the interpreter explicitly: `--python /path/to/python`
- Or set `PROAGENT_PYTHON=/path/to/python`

### Relative paths for `--load-session` / `--config`

Use absolute paths if you’re unsure. The backend may resolve relative paths from `agent_orchestrator/` depending on how it was launched.

