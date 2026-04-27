"""
JSON-line backend for the Ink CLI.

Protocol:
  - Reads JSON commands from stdin (one per line)
  - Writes JSON events to stdout (one per line)
  - All Python logging / print output goes to stderr

Commands (stdin):
  load_config       {to_number, from_number?, call_direction?, config_overrides?}
  load_config_file  {path}
  load_session      {path}
  send_message      {text}
  get_state         {}
  get_transcript    {}
  get_context       {}  -- full chat context as the LLM sees it
  get_prompt        {}  -- current assembled system + state prompt
  end_call          {}
  shutdown          {}

Events (stdout):
  ready             {version}
  config_loaded     {call_id, config_source, starting_state, first_message}
  stream_start      {}
  stream_chunk      {text}
  stream_end        {}
  tool_calls        {tool_calls: [{tool_call_id, name, arguments, result}]}
  state_changed     {state}
  context           {messages: [...]}
  prompt            {prompt}
  call_ended        {transcript}
  error             {message, code?}
"""

import asyncio
import builtins
import json
import logging
import os
import sys
import time
import uuid
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Verbose mode (CLI-only)
# ---------------------------------------------------------------------------

_CLI_VERBOSE = os.environ.get("PROAGENT_CLI_VERBOSE", "").lower() in (
    "1",
    "true",
    "yes",
    "y",
)

# ---------------------------------------------------------------------------
# Redirect ALL output to stderr BEFORE importing anything from agent_orchestrator
# ---------------------------------------------------------------------------

_original_stdout = sys.stdout
# Create a NEW file object from fd 1 (stdout) so no library can intercept it
_event_writer = os.fdopen(os.dup(sys.stdout.fileno()), "w")
sys.stdout = sys.stderr  # everything else (print, logs) → stderr

# Override builtins.print so third-party / internal prints go to stderr
_original_print = builtins.print


def _stderr_print(*args, **kwargs):
    kwargs.setdefault("file", sys.stderr)
    _original_print(*args, **kwargs)


builtins.print = _stderr_print

# Configure root logger → stderr
logging.basicConfig(
    level=logging.DEBUG if _CLI_VERBOSE else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
    force=True,
)

# ---------------------------------------------------------------------------
# Path setup — navigate from cli/ to agent_orchestrator/
# ---------------------------------------------------------------------------

_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)  # cli/ → project root
_agent_dir = os.path.join(_project_root, "agent_orchestrator")

# Load .env if present (before importing Config)
try:
    from dotenv import load_dotenv

    env_path = os.path.join(_agent_dir, ".env.local")
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        env_path2 = os.path.join(_agent_dir, ".env")
        if os.path.exists(env_path2):
            load_dotenv(env_path2)
except ImportError:
    pass

# Ensure agent_orchestrator/ is on sys.path (needed when run directly)
if _agent_dir not in sys.path:
    sys.path.insert(0, _agent_dir)
os.chdir(_agent_dir)

# Now safe to import project modules
from livekit.agents import AgentSession  # noqa: E402
from livekit.agents.llm import ChatContext  # noqa: E402
from livekit.agents.llm.chat_context import (  # noqa: E402
    ChatMessage,
    FunctionCall,
    FunctionCallOutput,
)

from custom_plugins.custom_llm.utils import (  # noqa: E402
    convert_chat_ctx_to_openai_format,
    create_custom_llm_chat_ctx,
)
from proagent.agent import DynamicVariablesWebhook, ProAgent  # noqa: E402
from proagent.prompts import (  # noqa: E402
    _check_conditions,
    get_greetings_and_rpc_system_message,
    get_state_system_prompt,
)
from proagent.state_loop import GreetingsAndRPCLoop  # noqa: E402
from proagent.utils import (  # noqa: E402
    check_if_state_transition_tool,
    get_config_from_db,
    get_state_name_from_tool_name,
)
from schemas.events import (  # noqa: E402
    AgentSessionUserData,
    ToolCallInvocationResponse,
    ToolCallResultResponse,
)
from schemas.types import (  # noqa: E402
    LLMTTFT,
    CallDirection,
    GreetingsAndRPCStateSpec,
    LLMUsage,
    ProAgentLLMConfig,
)

logger = logging.getLogger("cli_backend")
logger.setLevel(logging.DEBUG if _CLI_VERBOSE else logging.INFO)

VERSION = "0.2.0"


# ---------------------------------------------------------------------------
# Event emitter — writes JSON lines to the original stdout
# ---------------------------------------------------------------------------


def emit(event: str, **data):
    """Write a single JSON-line event to the Ink CLI."""
    payload = {"event": event, **data}
    line = json.dumps(payload, ensure_ascii=False)
    _event_writer.write(line + "\n")
    _event_writer.flush()


def emit_error(message: str, code: Optional[str] = None):
    emit("error", message=message, **({"code": code} if code else {}))


# ---------------------------------------------------------------------------
# Deep merge for config overrides
# ---------------------------------------------------------------------------


def deep_merge(base: dict, overrides: dict) -> dict:
    """Recursively merge *overrides* into *base* (non-mutating)."""
    result = deepcopy(base)
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


# ---------------------------------------------------------------------------
# Inlined from simulator/core.py — MockCallService, generate_call_id,
# _create_session, _parse_transcript
# ---------------------------------------------------------------------------


class MockCallService:
    """Mock call service for simulation - stubs out call operations."""

    def __init__(self):
        self._agent_session = None
        self.events: List[Any] = []

    def add_event(self, event):
        """Record CallEvents emitted by state loops (e.g. GreetingsAndRPCLoop's
        rpc_verification_started/completed/failed) so they don't crash the simulator."""
        self.events.append(event)
        try:
            logger.info(
                "call_event: name=%s source=%s value=%s",
                getattr(event, "event_name", "?"),
                getattr(event, "source", "?"),
                getattr(event, "value", {}),
            )
        except Exception:
            pass

    async def update_call_details_in_redis(self, details: dict):
        pass

    async def transfer_call(self, request):
        pass

    async def end_call(self, end_reason: str):
        pass


def generate_call_id() -> str:
    """Generate a unique call ID for simulation."""
    id = str(uuid.uuid4())[:7]
    return f"call_simulation_{id}"


def _parse_transcript(
    chat_ctx: ChatContext, transcript: List[Dict]
) -> Tuple[
    List[Tuple[str, Optional[str]]],
    Dict[str, ToolCallInvocationResponse],
    Dict[str, ToolCallResultResponse],
]:
    """
    Parse transcript and extract messages and tool call data.

    Populates *chat_ctx* with user/assistant messages from the transcript and
    returns tool-call tracking structures for AgentSessionUserData.
    """
    tool_call_ids: List[Tuple[str, Optional[str]]] = []
    tool_call_invocations: Dict[str, ToolCallInvocationResponse] = {}
    tool_call_results: Dict[str, ToolCallResultResponse] = {}

    if not transcript:
        return tool_call_ids, tool_call_invocations, tool_call_results

    last_message_id: Optional[str] = None
    message_counter = 0

    for item in transcript:
        role = item.get("role")
        created_at = item.get("created_at", int(time.time() * 1000))

        if role == "user":
            message_id = f"msg_{message_counter}"
            message_counter += 1
            chat_ctx.add_message(
                role="user",
                content=item.get("content", ""),
                id=message_id,
            )
            last_message_id = message_id

        elif role in ("assistant", "agent"):
            message_id = f"msg_{message_counter}"
            message_counter += 1
            chat_ctx.add_message(
                role="assistant",
                content=item.get("content", ""),
                id=message_id,
            )
            last_message_id = message_id

            tool_calls_list = item.get("tool_calls", [])
            for tool_call in tool_calls_list:
                tool_call_id = tool_call.get("id", "")
                function_data = tool_call.get("function", {})

                tool_call_ids.append((tool_call_id, last_message_id))

                tool_call_invocations[tool_call_id] = ToolCallInvocationResponse(
                    response_id=0,
                    tool_call_id=tool_call_id,
                    name=function_data.get("name", ""),
                    arguments=function_data.get("arguments", "{}"),
                    created_at=created_at,
                    pre_tool_call_text_length=item.get("pre_tool_call_text_length", 0),
                )

        elif role == "tool":
            tool_call_id = item.get("tool_call_id", "")
            tool_call_results[tool_call_id] = ToolCallResultResponse(
                response_id=0,
                tool_call_id=tool_call_id,
                content=item.get("content", ""),
                created_at=created_at,
            )

    return tool_call_ids, tool_call_invocations, tool_call_results


def _create_session(chat_ctx: ChatContext, transcript: List[Dict]) -> AgentSession:
    """
    Create a mock AgentSession for text-only simulation.

    Parses *transcript* into *chat_ctx* and builds the session with the
    extracted tool-call tracking data.
    """
    tool_call_ids, tool_call_invocations, tool_call_results = _parse_transcript(
        chat_ctx, transcript
    )

    userdata = AgentSessionUserData(
        tool_call_ids=tool_call_ids,
        tool_call_invocations=tool_call_invocations,
        tool_call_results=tool_call_results,
    )

    session = AgentSession[AgentSessionUserData](
        userdata=userdata,
        turn_detection="manual",
        allow_interruptions=False,
        min_interruption_duration=0.5,
        min_interruption_words=0,
        min_endpointing_delay=0.5,
        max_endpointing_delay=3.0,
        user_away_timeout=None,
        false_interruption_timeout=None,
    )

    return session


def _build_chat_ctx_from_openai_messages(messages: List[Dict]) -> ChatContext:
    """Build a ChatContext directly from OpenAI-format messages.

    Creates ChatMessage, FunctionCall, and FunctionCallOutput items
    directly — bypassing _parse_transcript and the lossy
    create_custom_llm_chat_ctx reconstruction.

    When tool_call_ids in session.userdata is empty,
    create_custom_llm_chat_ctx passes items through as-is,
    and convert_chat_ctx_to_utterances handles all three types natively.
    """
    chat_ctx = ChatContext.empty()
    now = time.time()

    for msg in messages:
        role = msg.get("role")

        if role in ("user", "system"):
            chat_ctx.items.append(
                ChatMessage(
                    role=role,
                    content=[msg.get("content", "")],
                    created_at=now,
                )
            )
        elif role in ("assistant", "agent"):
            content = msg.get("content", "")
            # Add the text part as a ChatMessage (even if empty — the
            # conversion pipeline expects an assistant message before tools)
            if content or "tool_calls" not in msg:
                chat_ctx.items.append(
                    ChatMessage(
                        role="assistant",
                        content=[content or ""],
                        created_at=now,
                    )
                )
            # Add each tool call as a FunctionCall item
            for tc in msg.get("tool_calls", []):
                func = tc.get("function", {})
                chat_ctx.items.append(
                    FunctionCall(
                        call_id=tc.get("id", ""),
                        name=func.get("name", ""),
                        arguments=func.get("arguments", ""),
                        created_at=now,
                    )
                )
        elif role == "tool":
            chat_ctx.items.append(
                FunctionCallOutput(
                    call_id=msg.get("tool_call_id", ""),
                    output=msg.get("content", ""),
                    is_error=False,
                    created_at=now,
                )
            )

    logger.info(
        "Built chat_ctx from %d OpenAI messages → %d items",
        len(messages),
        len(chat_ctx.items),
    )
    return chat_ctx


# ---------------------------------------------------------------------------
# Backend state — holds ProAgent components directly
# ---------------------------------------------------------------------------


class BackendState:
    def __init__(self):
        self.agent: Optional[ProAgent] = None
        self.chat_ctx: Optional[ChatContext] = None
        self.session: Optional[AgentSession] = None
        self.call_service: Optional[MockCallService] = None
        self.call_id: Optional[str] = None
        self.config: Optional[Dict[str, Any]] = None
        self.config_source: Optional[str] = None
        self.last_state: Optional[str] = None
        # Track transcript length to diff tool calls after each turn
        self.transcript_snapshot: List[Dict] = []
        # Rewind support: state & dynamic vars tracking
        # Each entry: (transcript_len, value) recorded at turn boundaries and state changes
        self.state_timeline: List[Tuple[int, str]] = []  # (transcript_len, state_name)
        self.dynamic_vars_snapshots: List[
            Tuple[int, Dict[str, Any]]
        ] = []  # (transcript_len, vars_copy)


state = BackendState()


# ---------------------------------------------------------------------------
# Config normalization
# ---------------------------------------------------------------------------


def normalize_config(raw: dict) -> dict:
    """
    Normalize a config dict into the format ProAgent expects.

    ProAgent needs:
      {tenant_id, from_number, to_number, call_direction, llm_config: {...}, metadata?}

    But local config files (like chat_config.json) are typically the llm_config
    itself (with llm_client, llm_model, states, general_prompt, etc. at top level).

    If the config already has "llm_config" as a nested dict, return as-is
    (with defaults for missing wrapper fields). Otherwise, wrap the whole
    thing as llm_config.
    """
    if "llm_config" in raw and isinstance(raw["llm_config"], dict):
        # Already in the wrapped format — just fill defaults
        raw.setdefault("from_number", "+10000000000")
        raw.setdefault("to_number", "+10000000001")
        raw.setdefault("call_direction", "inbound")
        raw.setdefault("tenant_id", raw.get("tenant_id", "simulator"))
        return raw

    # The raw config IS the llm_config — wrap it
    tenant_id = raw.pop("tenant_id", "simulator")
    return {
        "tenant_id": tenant_id,
        "from_number": "+10000000000",
        "to_number": "+10000000001",
        "call_direction": "inbound",
        "llm_config": raw,
        "metadata": {},
    }


# ---------------------------------------------------------------------------
# Tool call diffing
# ---------------------------------------------------------------------------


def _get_full_transcript() -> List[Dict]:
    """Get the full transcript with tool calls in OpenAI format."""
    if not state.agent or not state.chat_ctx or not state.session:
        return []
    custom_llm_chat_ctx = create_custom_llm_chat_ctx(
        state.chat_ctx, state.session.userdata
    )
    _, transcript_with_tool_calls = convert_chat_ctx_to_openai_format(
        custom_llm_chat_ctx
    )
    return transcript_with_tool_calls


def _diff_and_emit_tool_calls():
    """
    Compare current transcript with snapshot to find new tool call entries.

    The transcript contains:
      - {"role": "assistant", "content": "...", "tool_calls": [{id, type, function: {name, arguments}}]}
      - {"role": "tool", "tool_call_id": "...", "content": "..."}

    We find new entries since the last snapshot and pair invocations with results.
    """
    if not state.agent:
        return

    current = _get_full_transcript()
    old_len = len(state.transcript_snapshot)
    new_entries = current[old_len:]
    state.transcript_snapshot = current

    logger.debug(
        "tool_call diff: snapshot_len=%d, current_len=%d, new_entries=%d",
        old_len,
        len(current),
        len(new_entries),
    )
    for i, entry in enumerate(new_entries):
        logger.debug(
            "  new[%d]: role=%s, has_tool_calls=%s, keys=%s",
            i,
            entry.get("role"),
            "tool_calls" in entry,
            list(entry.keys()),
        )

    if not new_entries:
        return

    # Collect tool call invocations from assistant messages
    invocations: Dict[str, Dict] = {}
    results: Dict[str, str] = {}

    for entry in new_entries:
        role = entry.get("role")
        if role in ("assistant", "agent") and "tool_calls" in entry:
            for tc in entry["tool_calls"]:
                tc_id = tc.get("id", "")
                func = tc.get("function", {})
                invocations[tc_id] = {
                    "tool_call_id": tc_id,
                    "name": func.get("name", ""),
                    "arguments": func.get("arguments", ""),
                }
        elif role == "tool":
            tc_id = entry.get("tool_call_id", "")
            results[tc_id] = entry.get("content", "")

    # Pair invocations with results
    if invocations:
        formatted = []
        for tc_id, inv in invocations.items():
            formatted.append(
                {
                    "tool_call_id": inv["tool_call_id"],
                    "name": inv["name"],
                    "arguments": inv["arguments"],
                    "result": results.get(tc_id, ""),
                }
            )
        logger.info(
            "Emitting %d tool_calls: %s", len(formatted), [f["name"] for f in formatted]
        )
        emit("tool_calls", tool_calls=formatted)
    else:
        logger.debug("No tool call invocations found in new entries")


def _transcript_to_frontend_messages(transcript: List[Dict]) -> List[Dict]:
    """Convert OpenAI-format transcript to frontend-displayable messages.

    Groups assistant text + tool calls together, and converts tool results
    into a paired format for display.
    """
    messages = []
    for msg in transcript:
        role = msg.get("role")
        if role == "user":
            content = msg.get("content", "")
            if content:  # skip empty user messages (greeting trigger)
                messages.append({"role": "user", "content": content})
        elif role in ("assistant", "agent"):
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls")
            entry: Dict[str, Any] = {"role": "assistant", "content": content or ""}
            if tool_calls:
                entry["tool_calls"] = [
                    {
                        "tool_call_id": tc.get("id", ""),
                        "name": tc.get("function", {}).get("name", ""),
                        "arguments": tc.get("function", {}).get("arguments", ""),
                        "result": "",
                    }
                    for tc in tool_calls
                ]
            messages.append(entry)
        elif role == "tool":
            # Find the matching assistant tool_call entry and fill in the result
            tc_id = msg.get("tool_call_id", "")
            result_content = msg.get("content", "")
            for prev in reversed(messages):
                if prev.get("tool_calls"):
                    for tc in prev["tool_calls"]:
                        if tc["tool_call_id"] == tc_id:
                            tc["result"] = result_content
                    break
    return messages


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


async def handle_load_config(data: dict):
    """Load config from the remote config manager service."""
    to_number = data.get("to_number", "")
    from_number = data.get("from_number", "+10000000000")
    call_direction = data.get("call_direction", "inbound")
    config_overrides = data.get("config_overrides")

    call_id = generate_call_id()

    try:
        logger.debug(
            {
                "event": "cli.load_config.start",
                "call_id": call_id,
                "to_number": to_number,
                "from_number": from_number,
                "call_direction": call_direction,
                "has_overrides": bool(config_overrides),
            }
        )
        raw_config = await get_config_from_db(
            phone_number=to_number,
            call_id=call_id,
            call_direction=call_direction,
        )
        logger.debug(
            {
                "event": "cli.load_config.fetched",
                "call_id": call_id,
                "has_raw_config": bool(raw_config),
                "raw_config_keys": list(raw_config.keys())
                if isinstance(raw_config, dict)
                else None,
            }
        )
    except Exception as e:
        emit_error(f"Failed to fetch remote config: {e}", code="CONFIG_FETCH_FAILED")
        return

    if not raw_config:
        emit_error("No config returned for that phone number", code="CONFIG_NOT_FOUND")
        return

    # Build the config dict that ProAgent expects.
    # get_config_from_db returns {llm_config: {...}, agent_config: {...}, tenant_id: ...}
    db_llm_config = raw_config.get("llm_config", {})
    if not db_llm_config:
        emit_error("Remote config has no llm_config", code="CONFIG_MISSING_LLM")
        return

    config = {
        "tenant_id": raw_config.get("tenant_id", ""),
        "from_number": from_number,
        "to_number": to_number,
        "call_direction": call_direction,
        "llm_config": db_llm_config,
        "metadata": raw_config.get("metadata", {}),
    }

    source = "remote"
    if config_overrides:
        logger.debug({"event": "cli.load_config.apply_overrides", "call_id": call_id})
        config = deep_merge(config, config_overrides)
        source = "merged"

    await _init_agent(config, call_id, source)


async def handle_load_config_file(data: dict):
    """Load config entirely from a local JSON file."""
    path = data.get("path", "")
    if not os.path.isabs(path):
        # Resolve relative to agent_orchestrator/ for backward compat
        path = os.path.join(_agent_dir, path)

    try:
        with open(path, "r") as f:
            raw = json.load(f)
    except FileNotFoundError:
        emit_error(f"Config file not found: {path}", code="FILE_NOT_FOUND")
        return
    except json.JSONDecodeError as e:
        emit_error(f"Invalid JSON in config file: {e}", code="INVALID_JSON")
        return

    config = normalize_config(raw)
    call_id = generate_call_id()
    await _init_agent(config, call_id, "local")


async def handle_load_session(data: dict):
    """Resume a saved session or replay a chat export against a config.

    Supports two formats:
      1. Session format: {config, transcript, currentState, callId, ...}
         — self-contained, config is embedded
      2. Chat export format: {messages (with index), current_state, call_id,
         resume_from, ...}
         — config-agnostic, requires a separate config via config_path or to_number

    When resume_from is a number, the transcript is sliced to [:resume_from+1].
    """
    path = data.get("path", "")
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)

    try:
        with open(path, "r") as f:
            session_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        emit_error(f"Failed to load session: {e}", code="SESSION_LOAD_FAILED")
        return

    resume_from = session_data.get("resume_from")

    # Auto-detect format: chat export has "messages" with "index" fields
    messages = session_data.get("messages", [])
    is_chat_export = (
        len(messages) > 0 and isinstance(messages[0], dict) and "index" in messages[0]
    )

    # --- Resolve config ---
    config = session_data.get("config")
    has_embedded_config = config and (
        "llm_config" in config or "llm_client" in config or "states" in config
    )

    if has_embedded_config:
        # Session format — config is embedded
        config = normalize_config(config)
    else:
        # Chat export or session without config — need external config
        config = await _resolve_external_config(data)
        if config is None:
            return  # error already emitted

    # --- Resolve transcript and metadata ---
    if is_chat_export:
        # Chat export format — strip index fields to get plain transcript
        transcript = [
            {k: v for k, v in msg.items() if k != "index"} for msg in messages
        ]
        call_id = session_data.get("call_id") or generate_call_id()
    else:
        # Original session format
        transcript = session_data.get("transcript", [])
        call_id = session_data.get("callId") or generate_call_id()

    # Apply resume_from: slice transcript up to and including that index
    if resume_from is not None and isinstance(resume_from, int):
        logger.info(
            f"resume_from={resume_from}, slicing transcript from {len(transcript)} to {resume_from + 1} messages"
        )
        transcript = transcript[: resume_from + 1]

    # Infer current_state from transition tool calls in the transcript,
    # falling back to the config's starting_state.
    llm_config = config.get("llm_config", {})
    starting_state = llm_config.get("starting_state", "")
    if transcript:
        timeline = _rebuild_state_timeline_from_transcript(transcript, starting_state)
        inferred_state = timeline[-1][1] if timeline else starting_state
    else:
        inferred_state = starting_state

    if inferred_state:
        config["current_state"] = inferred_state
        logger.info(f"Inferred current_state from transcript: {inferred_state}")

    # Inject transcript and dynamic vars into config for reconstruction
    config["transcript"] = transcript
    dynamic_vars = session_data.get("dynamic_vars")
    if dynamic_vars:
        config["dynamic_vars"] = dynamic_vars

    await _init_agent(config, call_id, "session")


async def _resolve_external_config(data: dict) -> Optional[dict]:
    """Load config from config_path or to_number provided in the command.

    Returns a normalized config dict, or None if config cannot be resolved
    (error is emitted in that case).
    """
    config_path = data.get("config_path")
    to_number = data.get("to_number")

    if config_path:
        # Load from local file
        if not os.path.isabs(config_path):
            config_path = os.path.join(_agent_dir, config_path)
        try:
            with open(config_path, "r") as f:
                raw = json.load(f)
        except FileNotFoundError:
            emit_error(f"Config file not found: {config_path}", code="FILE_NOT_FOUND")
            return None
        except json.JSONDecodeError as e:
            emit_error(f"Invalid JSON in config file: {e}", code="INVALID_JSON")
            return None
        return normalize_config(raw)

    elif to_number:
        # Fetch from remote config service
        from_number = data.get("from_number", "+10000000000")
        call_id = generate_call_id()
        try:
            raw_config = await get_config_from_db(
                phone_number=to_number,
                call_id=call_id,
                call_direction="inbound",
            )
        except Exception as e:
            emit_error(
                f"Failed to fetch remote config: {e}", code="CONFIG_FETCH_FAILED"
            )
            return None
        if not raw_config or not raw_config.get("llm_config"):
            emit_error(
                "No config returned for that phone number", code="CONFIG_NOT_FOUND"
            )
            return None
        return {
            "tenant_id": raw_config.get("tenant_id", ""),
            "from_number": from_number,
            "to_number": to_number,
            "call_direction": "inbound",
            "llm_config": raw_config["llm_config"],
            "metadata": raw_config.get("metadata", {}),
        }

    else:
        emit_error(
            "Chat export requires a config. "
            "Use --config <path> or --to-number <number> alongside --load-session.",
            code="SESSION_NO_CONFIG",
        )
        return None


def _rebuild_state_timeline_from_transcript(
    transcript: List[Dict], starting_state: str
) -> List[Tuple[int, str]]:
    """Reconstruct state timeline by scanning transcript for transition tool calls.

    State transitions use tools prefixed with "transition_to_" (e.g. transition_to_conversation).
    Also handles conditional edge transitions that inject synthetic tool calls.
    Returns a list of (transcript_index, state_name) entries.
    """
    timeline: List[Tuple[int, str]] = [(0, starting_state)]

    for i, msg in enumerate(transcript):
        role = msg.get("role")
        # Check assistant messages for transition tool calls
        if role in ("assistant", "agent"):
            for tc in msg.get("tool_calls", []):
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                if check_if_state_transition_tool(tool_name):
                    new_state = get_state_name_from_tool_name(tool_name)
                    if new_state:
                        timeline.append((i + 1, new_state))
        # Also check tool results that mention transitions (synthetic edges)
        elif role == "tool":
            content = msg.get("content", "")
            if content and "Transitioned to" in content:
                # Format: 'Transitioned to "state_name" state'
                try:
                    new_state = content.split('"')[1]
                    if new_state:
                        timeline.append((i + 1, new_state))
                except (IndexError, ValueError):
                    pass

    logger.info(
        "Rebuilt state timeline from transcript (%d messages): %s",
        len(transcript),
        [(t, s) for t, s in timeline],
    )
    return timeline


def _build_agent(config: dict, call_id: str) -> Tuple[ProAgent, MockCallService]:
    """Create a fresh ProAgent and MockCallService from config.

    Handles current_state and dynamic_vars overrides from config.
    Returns (agent, call_service).
    """
    call_service = MockCallService()
    dynamic_variables_webhook = DynamicVariablesWebhook(
        call_id=call_id,
        tenant_id=config["tenant_id"],
        from_number=config["from_number"],
        to_number=config["to_number"],
        call_direction=CallDirection(config["call_direction"]),
        llm_config=ProAgentLLMConfig(**config["llm_config"]),
        metadata=config.get("metadata", {}),
        should_prefetch_webhook_data=False,
    )
    agent = ProAgent(
        call_id=call_id,
        tenant_id=config["tenant_id"],
        from_number=config["from_number"],
        to_number=config["to_number"],
        call_direction=CallDirection(config["call_direction"]),
        proagent_llm_config=ProAgentLLMConfig(**config["llm_config"]),
        call_service=call_service,
        metadata=config.get("metadata", {}),
        dynamic_variables_webhook=dynamic_variables_webhook,
    )

    # Handle current_state override
    if "current_state" in config:
        logger.info(f"Setting current state to {config['current_state']}")
        agent.state_manager.current_state = config["current_state"]

    # Restore dynamic variables if present (from chat export / session / rewind)
    if "dynamic_vars" in config and config["dynamic_vars"]:
        logger.info("Restoring %d dynamic variables", len(config["dynamic_vars"]))
        agent.state_manager.dynamic_vars.update(config["dynamic_vars"])

    return agent, call_service


async def _init_agent(config: dict, call_id: str, source: str):
    """Create a ProAgent directly and emit config_loaded."""
    try:
        logger.debug(
            {
                "event": "cli.init_agent.start",
                "call_id": call_id,
                "source": source,
                "starting_state_override": config.get("current_state"),
            }
        )
        agent, call_service = _build_agent(config, call_id)

        transcript = config.get("transcript", [])

        if transcript:
            logger.debug(
                {
                    "event": "cli.init_agent.resume_mode",
                    "call_id": call_id,
                    "transcript_len": len(transcript),
                }
            )
            # Loaded session — build chat_ctx directly from the OpenAI-format
            # messages so they pass through create_custom_llm_chat_ctx unchanged.
            chat_ctx = _build_chat_ctx_from_openai_messages(transcript)
            session = _create_session(ChatContext.empty(), [])  # empty userdata
        else:
            logger.debug({"event": "cli.init_agent.fresh_mode", "call_id": call_id})
            # Fresh session
            chat_ctx = ChatContext.empty()
            session = _create_session(chat_ctx, [])

        # Store in global state
        state.agent = agent
        state.chat_ctx = chat_ctx
        state.session = session
        state.call_service = call_service
        state.call_id = call_id
        state.config = config
        state.config_source = source
        state.last_state = agent.state_manager.current_state
        state.transcript_snapshot = []
        # Seed rewind timeline — rebuild from transcript if resuming a session,
        # otherwise just record the starting state.
        if transcript:
            # Determine the starting state of the conversation (before any transitions).
            # The config's llm_config has the starting_state, which is the state before
            # any transitions occurred in the original conversation.
            llm_config = config.get("llm_config", {})
            original_starting_state = llm_config.get(
                "starting_state", agent.state_manager.current_state
            )
            state.state_timeline = _rebuild_state_timeline_from_transcript(
                transcript, original_starting_state
            )
        else:
            state.state_timeline = [(0, agent.state_manager.current_state)]
        state.dynamic_vars_snapshots = [(0, deepcopy(agent.state_manager.dynamic_vars))]

        if transcript:
            # Loaded session — call state_loop.run() directly instead of
            # agent.run(). agent.run() has an outer while-True that continues
            # to new states after a state transition, which causes the new
            # state to generate a greeting.  By using the state loop directly,
            # we run ONE state and stop.

            # Mark webhook processed so it doesn't overwrite restored dynamic_vars
            agent.processed_webhook = True
            agent.webhook_process_task = asyncio.ensure_future(asyncio.sleep(0))

            curr_state = agent.state_manager.current_state
            curr_state_loop = agent.state_loops[curr_state]
            last_msg_id = chat_ctx.items[-1].id if chat_ctx.items else None

            # Convert loaded messages to frontend-displayable format
            loaded_messages = _transcript_to_frontend_messages(transcript)

            # IMPORTANT: Tell the UI about the loaded history BEFORE we stream the
            # "next" assistant message. Otherwise, the UI appends the loaded
            # transcript *after* the streamed message, which looks like the
            # conversation "restarted".
            dp_index, dp_condition = _get_dynamic_prompt_info()
            emit(
                "config_loaded",
                call_id=call_id,
                config_source=source,
                starting_state=state.agent.state_manager.current_state,
                first_message="",
                config=_safe_serialize(config),
                loaded_messages=loaded_messages,
                dynamic_prompt_index=dp_index,
                dynamic_prompt_condition=dp_condition,
            )

            # Seed the transcript snapshot so we only emit tool_calls for NEW
            # entries produced after resume (prevents re-emitting historical tools).
            state.transcript_snapshot = _get_full_transcript()

            streaming = False
            saw_usage = False

            async for chunk in curr_state_loop.run(
                chat_ctx,
                session,
                original_last_message_id=last_msg_id,
            ):
                if isinstance(chunk, LLMTTFT):
                    if _CLI_VERBOSE:
                        logger.debug(
                            {
                                "event": "cli.llm_ttft",
                                "call_id": call_id,
                                "ttft_seconds": chunk.ttft,
                            }
                        )
                    continue
                if isinstance(chunk, LLMUsage):
                    if streaming:
                        emit("stream_end")
                        streaming = False
                    saw_usage = True
                    continue
                if chunk and chunk.delta and chunk.delta.content:
                    if saw_usage:
                        _diff_and_emit_tool_calls()
                        _check_state_change()
                        saw_usage = False
                    if not streaming:
                        emit("stream_start")
                        streaming = True
                    emit("stream_chunk", text=chunk.delta.content)
            if streaming:
                emit("stream_end")
            _diff_and_emit_tool_calls()

            # Update state if the state loop triggered a transition
            if curr_state_loop.transitioned_to_state:
                agent.state_manager.current_state = (
                    curr_state_loop.transitioned_to_state
                )
            _check_state_change()

            # Record turn-end state for rewind support
            _record_turn_end()

        else:
            # Fresh session — add empty user message to trigger greeting
            state.chat_ctx.add_message(role="user", content="")

            first_message = ""
            streaming = False
            saw_usage = False
            # Track text segments for post-transition reconciliation
            current_segment: List[str] = []
            last_complete_segment: str = ""
            tick_task: asyncio.Task | None = None
            if _CLI_VERBOSE:

                async def _tick():
                    waited = 0
                    while True:
                        await asyncio.sleep(2)
                        waited += 2
                        logger.debug(
                            {
                                "event": "cli.init_agent.waiting_for_first_output",
                                "call_id": call_id,
                                "waited_seconds": waited,
                            }
                        )

                tick_task = asyncio.create_task(_tick())

            async for chunk in state.agent.run(state.chat_ctx, state.session):
                if tick_task:
                    tick_task.cancel()
                    tick_task = None
                if isinstance(chunk, LLMTTFT):
                    if _CLI_VERBOSE:
                        logger.debug(
                            {
                                "event": "cli.llm_ttft",
                                "call_id": call_id,
                                "ttft_seconds": chunk.ttft,
                            }
                        )
                    continue
                if isinstance(chunk, LLMUsage):
                    if streaming:
                        emit("stream_end")
                        streaming = False
                    if current_segment:
                        last_complete_segment = "".join(current_segment)
                        current_segment = []
                    saw_usage = True
                    continue
                if chunk and chunk.delta and chunk.delta.content:
                    if saw_usage:
                        _diff_and_emit_tool_calls()
                        _check_state_change()
                        saw_usage = False
                    if not streaming:
                        emit("stream_start")
                        streaming = True
                    first_message += chunk.delta.content
                    current_segment.append(chunk.delta.content)
                    emit("stream_chunk", text=chunk.delta.content)
            if streaming:
                emit("stream_end")
            if current_segment:
                last_complete_segment = "".join(current_segment)
            _diff_and_emit_tool_calls()
            _check_state_change()
            _reconcile_chat_ctx(last_complete_segment)

            # Record turn-end state for rewind support
            _record_turn_end()

            dp_index, dp_condition = _get_dynamic_prompt_info()
            emit(
                "config_loaded",
                call_id=call_id,
                config_source=source,
                starting_state=state.agent.state_manager.current_state,
                first_message=first_message,
                config=_safe_serialize(config),
                dynamic_prompt_index=dp_index,
                dynamic_prompt_condition=dp_condition,
            )
    except Exception as e:
        logger.exception("Failed to initialize agent")
        emit_error(f"Failed to initialize: {e}", code="INIT_FAILED")


async def handle_send_message(data: dict):
    """Stream a response to a user message."""
    if not state.agent:
        emit_error("No active session. Load a config first.", code="NO_SESSION")
        return

    text = data.get("text", "")
    streaming = False
    saw_usage = False
    # Track text for the current streaming segment so we can reconcile
    # the chat context after a state transition (the state_loop may not
    # add post-transition text to the context).
    current_segment: List[str] = []
    last_complete_segment: str = ""

    try:
        state.chat_ctx.add_message(role="user", content=text)
        async for chunk in state.agent.run(state.chat_ctx, state.session):
            if isinstance(chunk, LLMTTFT):
                if _CLI_VERBOSE:
                    logger.debug(
                        {
                            "event": "cli.llm_ttft",
                            "call_id": state.call_id,
                            "ttft_seconds": chunk.ttft,
                        }
                    )
                continue
            if isinstance(chunk, LLMUsage):
                # End of an LLM call. Tool execution happens in the gap
                # AFTER this, before the next text chunk arrives.
                if streaming:
                    emit("stream_end")
                    streaming = False
                # Save the completed segment
                if current_segment:
                    last_complete_segment = "".join(current_segment)
                    current_segment = []
                saw_usage = True
                continue
            if chunk and chunk.delta and chunk.delta.content:
                # First text after a usage gap — tool calls are now in userdata
                if saw_usage:
                    _diff_and_emit_tool_calls()
                    _check_state_change()
                    saw_usage = False
                if not streaming:
                    emit("stream_start")
                    streaming = True
                current_segment.append(chunk.delta.content)
                emit("stream_chunk", text=chunk.delta.content)
    except Exception as e:
        logger.exception("Error during streaming")
        emit_error(f"Streaming error: {e}", code="STREAM_ERROR")

    if streaming:
        emit("stream_end")
    # Save any trailing segment (text after last LLMUsage)
    if current_segment:
        last_complete_segment = "".join(current_segment)
    # Final check — catches tool calls from the last LLM iteration
    _diff_and_emit_tool_calls()
    _check_state_change()

    # Reconcile: when agent.run() spans multiple states
    # (continue_after_transition), the post-transition state's text may
    # not be added to the chat context by state_loop.  Patch the gap so
    # subsequent turns see the full conversation.
    _reconcile_chat_ctx(last_complete_segment)

    # Record turn-end state and dynamic vars for rewind support
    _record_turn_end()
    if state.agent:
        transcript_len = len(_get_full_transcript())
        dv_copy = deepcopy(state.agent.state_manager.dynamic_vars)
        state.dynamic_vars_snapshots.append((transcript_len, dv_copy))


async def handle_get_state(_data: dict):
    if not state.agent:
        emit_error("No active session", code="NO_SESSION")
        return
    emit("state_changed", state=state.agent.state_manager.current_state)


async def handle_get_transcript(_data: dict):
    if not state.agent:
        emit_error("No active session", code="NO_SESSION")
        return
    transcript = _get_full_transcript()
    emit("transcript", transcript=transcript)


async def handle_get_context(_data: dict):
    """Return the full chat context as the LLM sees it — messages + tool calls."""
    if not state.agent:
        emit_error("No active session", code="NO_SESSION")
        return

    custom_llm_chat_ctx = create_custom_llm_chat_ctx(
        state.chat_ctx, state.session.userdata
    )
    _, transcript_with_tool_calls = convert_chat_ctx_to_openai_format(
        custom_llm_chat_ctx
    )
    emit(
        "context",
        messages=transcript_with_tool_calls,
        dynamic_vars=_safe_serialize(state.agent.state_manager.dynamic_vars),
        current_state=state.agent.state_manager.current_state,
    )


async def handle_get_prompt(_data: dict):
    """Return the current assembled system + state prompt with variables substituted."""
    if not state.agent:
        emit_error("No active session", code="NO_SESSION")
        return

    sm = state.agent.state_manager
    llm_config = state.agent.proagent_llm_config
    spec = sm.current_state_spec

    if isinstance(spec, GreetingsAndRPCStateSpec):
        loop = state.agent.state_loops.get(sm.current_state)
        current_stage = None
        verified_fields: set = set()
        exhausted_fields: set = set()
        verification_failed = False
        if isinstance(loop, GreetingsAndRPCLoop):
            stages = loop.pii_stages
            idx = loop._current_pii_stage
            current_stage = stages[idx] if idx < len(stages) else None
            verified_fields = loop._verified_fields
            exhausted_fields = loop._exhausted_fields
            verification_failed = loop.is_verification_failed
        prompt = get_greetings_and_rpc_system_message(
            state_spec=spec,
            current_verification_stage=current_stage,
            verified_fields=verified_fields,
            exhausted_fields=exhausted_fields,
            verification_failed=verification_failed,
            dynamic_vars=sm.dynamic_vars,
        )
    else:
        prompt = get_state_system_prompt(
            general_prompt=llm_config.general_prompt,
            state_prompt=spec.state_prompt,
            dynamic_vars=sm.dynamic_vars,
        )

    emit(
        "prompt",
        prompt=prompt,
        state=sm.current_state,
        dynamic_vars=_safe_serialize(sm.dynamic_vars),
    )


async def handle_end_call(_data: dict):
    if not state.agent:
        emit_error("No active session", code="NO_SESSION")
        return
    transcript = _get_full_transcript()
    emit("call_ended", transcript=transcript)
    state.agent = None
    state.chat_ctx = None
    state.session = None
    state.call_service = None


async def handle_rewind(data: dict):
    """Rewind conversation to a specific transcript index.

    Recreates the ProAgent from scratch to ensure all internal state
    (state loops, PII verification stages, etc.) is completely fresh.
    """
    if not state.agent or not state.config:
        emit_error("No active session. Load a config first.", code="NO_SESSION")
        return

    index = data.get("index")
    if index is None or not isinstance(index, int) or index < 0:
        emit_error("Invalid rewind index", code="INVALID_REWIND_INDEX")
        return

    try:
        # 1. Get the full transcript and validate index
        full_transcript = _get_full_transcript()
        if index >= len(full_transcript):
            emit_error(
                f"Rewind index {index} out of range (transcript has {len(full_transcript)} messages)",
                code="REWIND_INDEX_OUT_OF_RANGE",
            )
            return

        # 2. Validate target is a user or assistant message
        target_role = full_transcript[index].get("role")
        if target_role not in ("user", "assistant", "agent"):
            emit_error(
                f"Cannot rewind to a '{target_role}' message. Select a user or assistant message.",
                code="REWIND_INVALID_TARGET",
            )
            return

        # 3. If the target assistant message has tool_calls, extend past
        #    the subsequent tool-result messages to keep the sequence intact.
        end_index = index + 1
        if target_role in ("assistant", "agent") and full_transcript[index].get(
            "tool_calls"
        ):
            while (
                end_index < len(full_transcript)
                and full_transcript[end_index].get("role") == "tool"
            ):
                end_index += 1

        truncated_transcript = full_transcript[:end_index]

        # 4. Determine the correct state for this point in history
        target_state = (
            state.state_timeline[0][1]
            if state.state_timeline
            else state.agent.state_manager.current_state
        )
        for tlen, sname in state.state_timeline:
            if tlen <= end_index:
                target_state = sname
            else:
                break

        # 5. Determine the correct dynamic_vars for this point
        target_dynamic_vars = (
            state.dynamic_vars_snapshots[0][1] if state.dynamic_vars_snapshots else {}
        )
        for tlen, dv in state.dynamic_vars_snapshots:
            if tlen <= end_index:
                target_dynamic_vars = dv
            else:
                break

        # 6. Recreate the ProAgent from scratch — this ensures ALL internal
        #    state (state loops, PII stages, cached tools, etc.) is fresh.
        rewind_config = deepcopy(state.config)
        rewind_config["current_state"] = target_state
        rewind_config["dynamic_vars"] = deepcopy(target_dynamic_vars)

        agent, call_service = _build_agent(rewind_config, state.call_id)

        # Prevent webhook from overwriting restored dynamic_vars on next run
        agent.processed_webhook = True
        agent.webhook_process_task = asyncio.ensure_future(asyncio.sleep(0))

        # 7. Rebuild chat_ctx from truncated transcript
        new_chat_ctx = _build_chat_ctx_from_openai_messages(truncated_transcript)

        # 8. Update global state with the fresh agent
        state.agent = agent
        state.call_service = call_service
        state.chat_ctx = new_chat_ctx
        state.session = _create_session(ChatContext.empty(), [])
        state.last_state = target_state
        # Use the truncated transcript directly as the snapshot — avoids
        # format mismatches from roundtripping through chat_ctx + empty userdata
        # which can produce a different entry count, breaking tool call diffing.
        state.transcript_snapshot = list(truncated_transcript)

        # 9. Prune timeline entries beyond the rewind point
        state.state_timeline = [
            (t, s) for t, s in state.state_timeline if t <= end_index
        ]
        state.dynamic_vars_snapshots = [
            (t, d) for t, d in state.dynamic_vars_snapshots if t <= end_index
        ]

        # 10. Emit rewind_complete with truncated messages for frontend display
        loaded_messages = _transcript_to_frontend_messages(truncated_transcript)
        emit(
            "rewind_complete",
            loaded_messages=loaded_messages,
            current_state=target_state,
            dynamic_vars=_safe_serialize(target_dynamic_vars),
        )

        logger.info(
            "Rewind complete: index=%d, state=%s, transcript_len=%d",
            index,
            target_state,
            len(truncated_transcript),
        )

    except Exception as e:
        logger.exception("Failed to rewind")
        emit_error(f"Rewind failed: {e}", code="REWIND_FAILED")


async def handle_shutdown(_data: dict):
    emit("shutdown_ack")
    # Give the event time to flush
    await asyncio.sleep(0.05)
    sys.exit(0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_dynamic_prompt_info() -> Tuple[Optional[int], Optional[str]]:
    """Detect which dynamic prompt variant is active for the current state.

    Uses the original config's dynamic_prompting definitions (since the
    orchestrator replaces the state spec after applying a variant, losing
    the dynamic_prompting field on the live spec).

    States in the config may be raw dicts (from JSON) or Pydantic model
    objects (after ProAgentLLMConfig parsing). Both are handled.

    Returns (index, condition_summary) or (None, None) if no dynamic prompting
    is configured or no condition matched.
    """
    if not state.agent or not state.config:
        return None, None
    sm = state.agent.state_manager
    current = sm.current_state
    dynamic_vars = sm.dynamic_vars

    llm_config = state.config.get("llm_config", {})
    states_config = llm_config.get("states", [])

    dynamic_prompting = None
    for s in states_config:
        if isinstance(s, dict):
            if s.get("name") == current:
                dynamic_prompting = s.get("dynamic_prompting")
                break
        else:
            # Pydantic model — access via attribute
            if getattr(s, "name", None) == current:
                dp = getattr(s, "dynamic_prompting", None)
                if dp:
                    dynamic_prompting = [
                        d if isinstance(d, dict) else (d.model_dump() if hasattr(d, "model_dump") else d)
                        for d in dp
                    ]
                break

    if not dynamic_prompting:
        return None, None

    for i, dp in enumerate(dynamic_prompting):
        conditions = dp.get("conditions", [])
        if _check_conditions(conditions, dynamic_vars):
            parts = []
            for c in conditions:
                key = c.get("key", "?")
                op = c.get("operator", "eq")
                val = c.get("value", "")
                if op == "exists":
                    parts.append(f"{key} exists")
                elif op == "not_exists":
                    parts.append(f"{key} !exists")
                elif op in ("any_in_array_eq", "none_in_array_eq"):
                    af = c.get("array_field", "")
                    parts.append(f"{key}[].{af} {op} {val}")
                else:
                    parts.append(f"{key}={val}")
            return i, " & ".join(parts)
    return None, None


def _check_state_change():
    """Emit state_changed if the agent state differs from last known."""
    if not state.agent:
        return
    current = state.agent.state_manager.current_state
    if current != state.last_state:
        state.last_state = current
        # Record mid-turn state change for rewind support
        state.state_timeline.append((len(state.transcript_snapshot), current))
        dp_index, dp_condition = _get_dynamic_prompt_info()
        emit(
            "state_changed",
            state=current,
            dynamic_prompt_index=dp_index,
            dynamic_prompt_condition=dp_condition,
        )


def _record_turn_end():
    """Record state and dynamic vars at the end of a complete turn.

    Called after _init_agent greeting, session resume, and each handle_send_message.
    Provides reliable turn-boundary snapshots for rewind.
    """
    if not state.agent:
        return
    transcript_len = len(_get_full_transcript())
    current = state.agent.state_manager.current_state
    # Only append if the position is new (avoid duplicates from _check_state_change)
    if not state.state_timeline or state.state_timeline[-1] != (
        transcript_len,
        current,
    ):
        state.state_timeline.append((transcript_len, current))


def _reconcile_chat_ctx(last_segment: str):
    """Ensure the last streamed text is present in the chat context.

    After a state transition with continuation, state_loop may not append
    the new state's generated text to the chat context.  Detect the gap
    and add a new assistant message so subsequent agent.run() calls see it.
    """
    if not last_segment or not last_segment.strip() or not state.chat_ctx:
        return

    # Walk backwards to find the last assistant message
    for item in reversed(state.chat_ctx.items):
        if hasattr(item, "role") and item.role == "assistant":
            if last_segment in (item.content[0] if item.content else ""):
                return  # Already present — nothing to do
            break  # Last assistant msg doesn't contain the text — need to add

    # The last streamed segment is missing from the context — add it
    state.chat_ctx.add_message(role="assistant", content=last_segment)
    logger.info(
        "Reconciled chat context: added missing post-transition text (%d chars)",
        len(last_segment),
    )


def _safe_serialize(obj: Any) -> Any:
    """Make an object JSON-safe (convert non-serializable types to strings)."""
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_safe_serialize(v) for v in obj]
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


# ---------------------------------------------------------------------------
# Command dispatcher
# ---------------------------------------------------------------------------

HANDLERS = {
    "load_config": handle_load_config,
    "load_config_file": handle_load_config_file,
    "load_session": handle_load_session,
    "send_message": handle_send_message,
    "get_state": handle_get_state,
    "get_transcript": handle_get_transcript,
    "get_context": handle_get_context,
    "get_prompt": handle_get_prompt,
    "end_call": handle_end_call,
    "rewind": handle_rewind,
    "shutdown": handle_shutdown,
}


async def process_line(line: str):
    """Parse a JSON command and dispatch to the appropriate handler."""
    line = line.strip()
    if not line:
        return

    try:
        data = json.loads(line)
    except json.JSONDecodeError as e:
        emit_error(f"Invalid JSON: {e}", code="INVALID_JSON")
        return

    command = data.get("command", "")
    handler = HANDLERS.get(command)
    if not handler:
        emit_error(f"Unknown command: {command}", code="UNKNOWN_COMMAND")
        return

    try:
        await handler(data)
    except Exception as e:
        logger.exception(f"Error handling command '{command}'")
        emit_error(f"Command error: {e}", code="COMMAND_ERROR")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


async def main():
    emit("ready", version=VERSION)

    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    transport, _ = await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader), sys.stdin
    )

    try:
        while True:
            line_bytes = await reader.readline()
            if not line_bytes:
                break  # EOF — parent process closed stdin
            line = line_bytes.decode("utf-8", errors="replace")
            await process_line(line)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception("Unexpected error in main loop")
        emit_error(f"Fatal: {e}", code="FATAL")
    finally:
        transport.close()


if __name__ == "__main__":
    asyncio.run(main())
