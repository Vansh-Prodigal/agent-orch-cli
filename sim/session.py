"""
Thin Python wrapper around `cli/backend.py`'s JSON-line protocol.

Lets a script drive a ProAgent conversation programmatically:

    s = Session(to_number="7066226252")
    print(s.start())          # first agent message after greeting
    print(s.say("Yes, this is Kelsey."))
    ...
    s.save_transcript("/tmp/foo.json")
    s.close()

The class spawns one long-lived Python backend per Session. All event
handling (stream_chunk, stream_end, tool_calls, state_changed, ...) is
collected per-turn and surfaced in the dict returned from `say()`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from queue import Empty, Queue
from typing import Any, Dict, List, Optional

CLI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PYTHON = os.environ.get(
    "PROAGENT_PYTHON",
    "/Users/vansh/Developer/agent-orchestrator/agent-orch/bin/python",
)


class BackendError(RuntimeError):
    pass


class Session:
    def __init__(
        self,
        to_number: str,
        from_number: str = "+10000000000",
        call_direction: str = "inbound",
        python_path: Optional[str] = None,
        cwd: Optional[str] = None,
        ready_timeout: float = 30.0,
        load_timeout: float = 90.0,
        turn_idle_seconds: float = 4.0,
        turn_timeout: float = 120.0,
        log_file: Optional[str] = None,
    ):
        self.to_number = to_number
        self.from_number = from_number
        self.call_direction = call_direction
        self.python_path = python_path or DEFAULT_PYTHON
        self.cwd = cwd or CLI_DIR
        self.ready_timeout = ready_timeout
        self.load_timeout = load_timeout
        self.turn_idle_seconds = turn_idle_seconds
        self.turn_timeout = turn_timeout

        self._events: "Queue[Dict[str, Any]]" = Queue()
        self._proc: Optional[subprocess.Popen] = None
        self._reader: Optional[threading.Thread] = None
        self._stderr_log = open(log_file, "w") if log_file else None
        self._stderr_reader: Optional[threading.Thread] = None
        self._closed = False
        self.config_loaded: Optional[Dict[str, Any]] = None
        self.first_message: str = ""
        self.current_state: Optional[str] = None

        self._spawn()

    # ------------------------------------------------------------------ spawn
    def _spawn(self) -> None:
        env = os.environ.copy()
        # Disable verbose to keep stderr quieter
        env.pop("PROAGENT_CLI_VERBOSE", None)
        self._proc = subprocess.Popen(
            [self.python_path, "backend.py"],
            cwd=self.cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()
        self._stderr_reader = threading.Thread(target=self._read_stderr, daemon=True)
        self._stderr_reader.start()

    def _read_stdout(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        for line in self._proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                self._events.put(json.loads(line))
            except json.JSONDecodeError:
                # non-JSON on stdout shouldn't happen, but log as stderr
                if self._stderr_log:
                    self._stderr_log.write(f"[non-json stdout] {line}\n")
                    self._stderr_log.flush()

    def _read_stderr(self) -> None:
        assert self._proc is not None and self._proc.stderr is not None
        for line in self._proc.stderr:
            if self._stderr_log:
                self._stderr_log.write(line)
                self._stderr_log.flush()

    # ------------------------------------------------------------------ I/O
    def _send(self, command: str, **payload: Any) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        msg = {"command": command, **payload}
        self._proc.stdin.write(json.dumps(msg) + "\n")
        self._proc.stdin.flush()

    def _wait_event(self, name: str, timeout: float) -> Dict[str, Any]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                evt = self._events.get(timeout=0.5)
            except Empty:
                if self._proc and self._proc.poll() is not None:
                    raise BackendError(
                        f"Backend exited (code {self._proc.returncode}) before {name}"
                    )
                continue
            if evt.get("event") == name:
                return evt
            if evt.get("event") == "error":
                raise BackendError(
                    f"Backend error: {evt.get('message')} (code {evt.get('code')})"
                )
        raise BackendError(f"Timed out waiting for {name}")

    def _drain_turn(self, timeout: float, idle: float) -> Dict[str, Any]:
        """Collect events from the queue until the agent's turn is settled.

        We consider the turn settled when no new events arrive for `idle` seconds
        AFTER we've seen at least one stream_end (or config_loaded for the
        bootstrap turn).
        """
        text = []
        tool_calls: List[Dict[str, Any]] = []
        state_changes: List[str] = []
        config_loaded: Optional[Dict[str, Any]] = None
        call_ended: Optional[Dict[str, Any]] = None
        loaded_messages: Optional[List[Dict[str, Any]]] = None
        terminated = False

        deadline = time.time() + timeout
        idle_until: Optional[float] = None
        seen_stream_end = False

        while time.time() < deadline:
            remaining = deadline - time.time()
            try:
                evt = self._events.get(timeout=min(0.5, max(0.05, remaining)))
            except Empty:
                if self._proc and self._proc.poll() is not None:
                    terminated = True
                    break
                if idle_until is not None and time.time() >= idle_until:
                    break
                continue
            etype = evt.get("event")
            if etype == "stream_chunk":
                text.append(evt.get("text", ""))
                idle_until = None
            elif etype == "stream_start":
                idle_until = None
            elif etype == "stream_end":
                seen_stream_end = True
                idle_until = time.time() + idle
            elif etype == "tool_calls":
                tool_calls.extend(evt.get("tool_calls", []))
                # keep waiting; tool calls usually precede or follow text
                idle_until = time.time() + idle
            elif etype == "state_changed":
                state_changes.append(evt.get("state"))
                self.current_state = evt.get("state")
            elif etype == "config_loaded":
                config_loaded = evt
                self.current_state = evt.get("starting_state")
                if "loaded_messages" in evt:
                    loaded_messages = evt.get("loaded_messages")
                # bootstrap turn — start idle window after config_loaded if not streaming
                if not text:
                    idle_until = time.time() + idle
            elif etype == "call_ended":
                call_ended = evt
                idle_until = time.time() + 0.5
                break
            elif etype == "error":
                raise BackendError(
                    f"Backend error: {evt.get('message')} (code {evt.get('code')})"
                )
            # ignore other events

        return {
            "text": "".join(text).strip(),
            "tool_calls": tool_calls,
            "state_changes": state_changes,
            "current_state": self.current_state,
            "config_loaded": config_loaded,
            "call_ended": call_ended,
            "loaded_messages": loaded_messages,
            "backend_exited": terminated,
        }

    # --------------------------------------------------------------- public
    def start(self) -> Dict[str, Any]:
        """Wait for backend ready, then load config and capture greeting."""
        self._wait_event("ready", self.ready_timeout)
        self._send(
            "load_config",
            to_number=self.to_number,
            from_number=self.from_number,
            call_direction=self.call_direction,
        )
        result = self._drain_turn(
            timeout=self.load_timeout, idle=self.turn_idle_seconds
        )
        if not result.get("config_loaded"):
            raise BackendError(
                "Did not receive config_loaded in time. "
                "Check stderr log; remote config fetch may have failed."
            )
        self.config_loaded = result["config_loaded"]
        self.first_message = result["text"]
        return result

    def say(self, text: str) -> Dict[str, Any]:
        if self._closed:
            raise BackendError("Session closed")
        self._send("send_message", text=text)
        return self._drain_turn(timeout=self.turn_timeout, idle=self.turn_idle_seconds)

    def get_transcript(self) -> List[Dict[str, Any]]:
        self._send("get_transcript")
        evt = self._wait_event("transcript", timeout=15.0)
        return evt.get("transcript", [])

    def end_call(self) -> Dict[str, Any]:
        self._send("end_call")
        return self._wait_event("call_ended", timeout=15.0)

    def save_transcript(
        self, path: str, extra: Optional[Dict[str, Any]] = None
    ) -> None:
        transcript = self.get_transcript()
        out = {
            "to_number": self.to_number,
            "starting_state": (
                self.config_loaded.get("starting_state") if self.config_loaded else None
            ),
            "current_state": self.current_state,
            "call_id": (
                self.config_loaded.get("call_id") if self.config_loaded else None
            ),
            "transcript": transcript,
        }
        if extra:
            out.update(extra)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._send("shutdown")
        except Exception:
            pass
        if self._proc:
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
        if self._stderr_log:
            self._stderr_log.close()

    # context manager
    def __enter__(self) -> "Session":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def pretty_print_turn(label: str, result: Dict[str, Any]) -> None:
    """Helper for debugging — prints a turn's outcome to stdout."""
    print(f"=== {label} ===")
    if result.get("text"):
        print(f"AGENT: {result['text']}")
    for tc in result.get("tool_calls", []):
        print(
            f"[tool] {tc.get('name')}({tc.get('arguments')}) -> {tc.get('result')[:200]}"
        )
    if result.get("state_changes"):
        print(f"[state] -> {result['state_changes'][-1]}")
    if result.get("call_ended"):
        print("[call ended]")
    print()


if __name__ == "__main__":
    # quick smoke-test driver: python session.py 7066226252
    if len(sys.argv) < 2:
        print("usage: session.py <to_number>", file=sys.stderr)
        sys.exit(2)
    s = Session(to_number=sys.argv[1], log_file="/tmp/session_smoketest.stderr")
    res = s.start()
    pretty_print_turn("greeting", res)
    s.close()
