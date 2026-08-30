#!/usr/bin/env python3
"""
Run live reference-number scenarios against the CLI backend and write a
self-refreshing HTML report after every significant event.
"""

from __future__ import annotations

import asyncio
import html
import json
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

CLI_DIR = Path(__file__).resolve().parents[2]
ARTEFACTS_DIR = Path(__file__).resolve().parent
BACKEND_PATH = CLI_DIR / "backend.py"
PYTHON_PATH = Path("/Users/vansh/Developer/agent-orchestrator/agent-orch/bin/python")
REPORT_PATH = ARTEFACTS_DIR / "reference-number-live-report.html"
DATA_PATH = ARTEFACTS_DIR / "reference-number-live-data.json"

TO_NUMBER = "7066226252"
REFERENCE_NUMBER = "70360256"
EXPECTED_CONSUMER_ID = "70360256"
EXPECTED_STATE = "s2a_verify_name"


def now_str() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def parse_json_maybe(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    try:
        return json.loads(text)
    except Exception:
        return value


def summarize_tool_result(result: Any) -> str:
    parsed = parse_json_maybe(result)
    if isinstance(parsed, dict):
        user_details = parsed.get("user_details")
        if isinstance(user_details, dict):
            consumer_id = user_details.get("consumer_id")
            first_name = user_details.get("first_name")
            last_name = user_details.get("last_name")
            if consumer_id:
                return (
                    f"consumer_id={consumer_id}, name={first_name} {last_name}".strip()
                )
        return compact_json(parsed)[:220]
    text = str(parsed)
    return text[:220]


def html_text(text: str) -> str:
    return html.escape(text, quote=True).replace("\n", "<br>")


@dataclass
class TimelineEntry:
    ts: str
    kind: str
    label: str
    text: str


@dataclass
class CheckResult:
    name: str
    passed: bool
    expected: str
    actual: str


@dataclass
class ScenarioSpec:
    key: str
    title: str
    description: str
    from_number: str
    expected: list[str]


@dataclass
class ScenarioRun:
    spec: ScenarioSpec
    status: str = "queued"
    verdict: str = "pending"
    call_id: str | None = None
    starting_state: str | None = None
    current_state: str | None = None
    first_message: str = ""
    assistant_messages: list[str] = field(default_factory=list)
    user_messages: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    timeline: list[TimelineEntry] = field(default_factory=list)
    checks: list[CheckResult] = field(default_factory=list)
    error: str | None = None
    context: dict[str, Any] | None = None
    raw_events_seen: int = 0
    _stream_chunks: list[str] = field(default_factory=list)

    def add_timeline(self, kind: str, label: str, text: str) -> None:
        self.timeline.append(
            TimelineEntry(ts=now_str(), kind=kind, label=label, text=text)
        )

    def add_user(self, text: str) -> None:
        self.user_messages.append(text)
        self.add_timeline("user", "User", text)

    def add_assistant(self, text: str) -> None:
        stripped = text.strip()
        if not stripped:
            return
        self.assistant_messages.append(stripped)
        self.add_timeline("assistant", "Assistant", stripped)

    def add_check(self, name: str, passed: bool, expected: str, actual: str) -> None:
        self.checks.append(
            CheckResult(name=name, passed=passed, expected=expected, actual=actual)
        )

    def has_failed(self) -> bool:
        return self.error is not None or any(not check.passed for check in self.checks)


class ReportWriter:
    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state
        self.lock = asyncio.Lock()

    async def write(self) -> None:
        async with self.lock:
            self.state["updated_at"] = now_str()
            payload = self._serialize_state()
            DATA_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            REPORT_PATH.write_text(self._render_html(payload), encoding="utf-8")

    def _serialize_state(self) -> dict[str, Any]:
        scenarios = []
        for run in self.state["scenarios"]:
            scenarios.append(
                {
                    "key": run.spec.key,
                    "title": run.spec.title,
                    "description": run.spec.description,
                    "from_number": run.spec.from_number,
                    "expected": run.spec.expected,
                    "status": run.status,
                    "verdict": run.verdict,
                    "call_id": run.call_id,
                    "starting_state": run.starting_state,
                    "current_state": run.current_state,
                    "first_message": run.first_message,
                    "checks": [
                        {
                            "name": check.name,
                            "passed": check.passed,
                            "expected": check.expected,
                            "actual": check.actual,
                        }
                        for check in run.checks
                    ],
                    "error": run.error,
                    "timeline": [
                        {
                            "ts": entry.ts,
                            "kind": entry.kind,
                            "label": entry.label,
                            "text": entry.text,
                        }
                        for entry in run.timeline
                    ],
                }
            )

        total_checks = sum(len(run.checks) for run in self.state["scenarios"])
        passed_checks = sum(
            1 for run in self.state["scenarios"] for check in run.checks if check.passed
        )
        passed_scenarios = sum(
            1 for run in self.state["scenarios"] if run.verdict == "pass"
        )

        return {
            "status": self.state["status"],
            "started_at": self.state["started_at"],
            "updated_at": self.state["updated_at"],
            "finished_at": self.state.get("finished_at"),
            "report_path": str(REPORT_PATH),
            "data_path": str(DATA_PATH),
            "to_number": TO_NUMBER,
            "reference_number": REFERENCE_NUMBER,
            "expected_consumer_id": EXPECTED_CONSUMER_ID,
            "expected_success_state": EXPECTED_STATE,
            "summary": {
                "scenario_count": len(self.state["scenarios"]),
                "passed_scenarios": passed_scenarios,
                "total_checks": total_checks,
                "passed_checks": passed_checks,
            },
            "scenarios": scenarios,
        }

    def _render_html(self, payload: dict[str, Any]) -> str:
        refresh = (
            '<meta http-equiv="refresh" content="1">'
            if payload["status"] != "complete"
            else ""
        )

        scenario_cards = "\n".join(
            self._render_scenario(s) for s in payload["scenarios"]
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  {refresh}
  <title>Reference Number Live Report</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #0f1115;
      --panel: #171a21;
      --border: #2a3040;
      --text: #e7ebf3;
      --muted: #a9b2c3;
      --pass: #1f8f55;
      --fail: #c24646;
      --run: #4c7bd9;
      --queued: #7b8190;
      --warn: #b8831d;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 24px;
    }}
    h1, h2, h3, p {{ margin: 0; }}
    .hero {{
      display: grid;
      gap: 16px;
      margin-bottom: 24px;
    }}
    .hero-card, .scenario {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
    }}
    .stat {{
      background: rgba(255,255,255,0.02);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px;
    }}
    .stat .label {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .stat .value {{
      font-size: 24px;
      font-weight: 700;
      margin-top: 4px;
    }}
    .muted {{
      color: var(--muted);
    }}
    .pill {{
      display: inline-block;
      border-radius: 999px;
      padding: 2px 10px;
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      border: 1px solid transparent;
    }}
    .pill.pass {{ background: rgba(31,143,85,0.18); color: #8dd4af; border-color: rgba(31,143,85,0.45); }}
    .pill.fail {{ background: rgba(194,70,70,0.18); color: #f1a3a3; border-color: rgba(194,70,70,0.45); }}
    .pill.running {{ background: rgba(76,123,217,0.18); color: #a7c0ff; border-color: rgba(76,123,217,0.45); }}
    .pill.queued {{ background: rgba(123,129,144,0.18); color: #c4c9d4; border-color: rgba(123,129,144,0.45); }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
    }}
    .scenario {{
      display: grid;
      gap: 14px;
    }}
    .scenario-header {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
    }}
    ul {{
      margin: 8px 0 0 18px;
      padding: 0;
    }}
    .checks {{
      display: grid;
      gap: 8px;
    }}
    .check {{
      border-left: 4px solid var(--border);
      padding: 8px 10px;
      background: rgba(255,255,255,0.02);
    }}
    .check.pass {{ border-color: var(--pass); }}
    .check.fail {{ border-color: var(--fail); }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }}
    th, td {{
      border-top: 1px solid var(--border);
      vertical-align: top;
      text-align: left;
      padding: 8px 6px;
    }}
    th {{
      color: var(--muted);
      font-weight: 600;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px;
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="hero-card">
        <h1>Reference Number Live Report</h1>
        <p class="muted">Testing the updated s1 behavior for reactive reference-number lookup on <code>{TO_NUMBER}</code>. This page refreshes every second while the run is active.</p>
      </div>
      <div class="stats">
        <div class="stat"><div class="label">Runner Status</div><div class="value">{html_text(payload["status"])}</div></div>
        <div class="stat"><div class="label">Passed Scenarios</div><div class="value">{payload["summary"]["passed_scenarios"]}/{payload["summary"]["scenario_count"]}</div></div>
        <div class="stat"><div class="label">Passed Checks</div><div class="value">{payload["summary"]["passed_checks"]}/{payload["summary"]["total_checks"]}</div></div>
        <div class="stat"><div class="label">Reference Number</div><div class="value"><code>{REFERENCE_NUMBER}</code></div></div>
      </div>
      <div class="hero-card">
        <p><strong>Started:</strong> {html_text(payload["started_at"])}</p>
        <p><strong>Updated:</strong> {html_text(payload["updated_at"])}</p>
        <p><strong>Expected success state:</strong> <code>{EXPECTED_STATE}</code></p>
        <p><strong>Expected consumer:</strong> <code>{EXPECTED_CONSUMER_ID}</code> / KELSEY HOWE</p>
      </div>
    </section>
    <section class="grid">
      {scenario_cards}
    </section>
  </main>
</body>
</html>
"""

    def _render_scenario(self, scenario: dict[str, Any]) -> str:
        status_class = {
            "pass": "pass",
            "fail": "fail",
            "running": "running",
            "queued": "queued",
            "pending": "queued",
        }.get(
            scenario["verdict"]
            if scenario["status"] == "complete"
            else scenario["status"],
            "queued",
        )

        checks_html = (
            "".join(
                f"""
            <div class="check {"pass" if check["passed"] else "fail"}">
              <div><strong>{html_text(check["name"])}</strong> <span class="pill {"pass" if check["passed"] else "fail"}">{"pass" if check["passed"] else "fail"}</span></div>
              <div class="muted"><strong>Expected:</strong> {html_text(check["expected"])}</div>
              <div><strong>Actual:</strong> {html_text(check["actual"])}</div>
            </div>
            """
                for check in scenario["checks"]
            )
            or '<div class="muted">No checks recorded yet.</div>'
        )

        timeline_rows = (
            "".join(
                f"""
            <tr>
              <td>{html_text(entry["ts"])}</td>
              <td>{html_text(entry["label"])}</td>
              <td>{html_text(entry["text"])}</td>
            </tr>
            """
                for entry in scenario["timeline"]
            )
            or '<tr><td colspan="3" class="muted">No events yet.</td></tr>'
        )

        expected_html = "".join(
            f"<li>{html_text(item)}</li>" for item in scenario["expected"]
        )

        call_meta = ""
        if scenario["call_id"]:
            call_meta += f"<p><strong>Call ID:</strong> <code>{html_text(scenario['call_id'])}</code></p>"
        if scenario["starting_state"]:
            call_meta += f"<p><strong>Start state:</strong> <code>{html_text(scenario['starting_state'])}</code></p>"
        if scenario["current_state"]:
            call_meta += f"<p><strong>Current state:</strong> <code>{html_text(scenario['current_state'])}</code></p>"
        if scenario["error"]:
            call_meta += (
                f"<p><strong>Error:</strong> {html_text(scenario['error'])}</p>"
            )

        return f"""
        <article class="scenario">
          <div class="scenario-header">
            <div>
              <h2>{html_text(scenario["title"])}</h2>
              <p class="muted">{html_text(scenario["description"])}</p>
              <p class="muted"><strong>ANI:</strong> <code>{html_text(scenario["from_number"])}</code></p>
            </div>
            <span class="pill {status_class}">{html_text(scenario["verdict"] if scenario["status"] == "complete" else scenario["status"])}</span>
          </div>
          <div>
            <h3>Expected Behavior</h3>
            <ul>{expected_html}</ul>
          </div>
          <div>
            <h3>Checks</h3>
            <div class="checks">{checks_html}</div>
          </div>
          <div>
            <h3>Run Metadata</h3>
            {call_meta or '<p class="muted">Waiting for session metadata.</p>'}
          </div>
          <div>
            <h3>Timeline</h3>
            <table>
              <thead>
                <tr><th>Time</th><th>Actor</th><th>Content</th></tr>
              </thead>
              <tbody>{timeline_rows}</tbody>
            </table>
          </div>
        </article>
        """


class BackendClient:
    def __init__(self, run: ScenarioRun, reporter: ReportWriter) -> None:
        self.run = run
        self.reporter = reporter
        self.proc: asyncio.subprocess.Process | None = None
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.stderr_tail: deque[str] = deque(maxlen=80)
        self.stdout_task: asyncio.Task[None] | None = None
        self.stderr_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self.proc = await asyncio.create_subprocess_exec(
            str(PYTHON_PATH),
            str(BACKEND_PATH),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(CLI_DIR),
            limit=10_000_000,
        )
        self.stdout_task = asyncio.create_task(self._read_stdout())
        self.stderr_task = asyncio.create_task(self._read_stderr())
        await self.wait_until(predicate=None, timeout=10, target_events={"ready"})

    async def _read_stdout(self) -> None:
        assert self.proc and self.proc.stdout
        while True:
            line = await self.proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            try:
                event = json.loads(text)
            except Exception:
                event = {"event": "parse_error", "message": text}
            await self.queue.put(event)

    async def _read_stderr(self) -> None:
        assert self.proc and self.proc.stderr
        while True:
            line = await self.proc.stderr.readline()
            if not line:
                break
            self.stderr_tail.append(line.decode("utf-8", errors="replace").rstrip())

    async def send(self, payload: dict[str, Any]) -> None:
        assert self.proc and self.proc.stdin
        self.proc.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        await self.proc.stdin.drain()

    async def send_message(self, text: str) -> None:
        self.run.add_user(text)
        await self.reporter.write()
        await self.send({"command": "send_message", "text": text})

    async def get_context(self) -> dict[str, Any]:
        await self.send({"command": "get_context"})
        event = await self.wait_until(
            lambda run: run.context is not None,
            timeout=30,
            target_events={"context", "error"},
        )
        return event

    async def wait_until(
        self,
        predicate: Callable[[ScenarioRun], bool] | None,
        timeout: float,
        target_events: set[str] | None = None,
    ) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout
        last_event: dict[str, Any] = {}
        while True:
            if predicate is not None and target_events is None and predicate(self.run):
                return last_event
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError(
                    f"Timed out in {self.run.spec.key}; stderr tail={list(self.stderr_tail)[-15:]}"
                )
            try:
                event = await asyncio.wait_for(
                    self.queue.get(), timeout=min(1.0, remaining)
                )
            except asyncio.TimeoutError:
                continue
            last_event = event
            await self._process_event(event)
            if event.get("event") == "error":
                raise RuntimeError(event.get("message", "Backend error"))
            if target_events is not None and event.get("event") not in target_events:
                continue
            if predicate is None or predicate(self.run):
                return event

    async def drain_until_idle(
        self, idle_seconds: float = 0.75, max_total: float = 4.0
    ) -> None:
        deadline = asyncio.get_running_loop().time() + max_total
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return
            try:
                event = await asyncio.wait_for(
                    self.queue.get(), timeout=min(idle_seconds, remaining)
                )
            except asyncio.TimeoutError:
                return
            await self._process_event(event)
            if event.get("event") == "error":
                raise RuntimeError(event.get("message", "Backend error"))

    async def _process_event(self, event: dict[str, Any]) -> None:
        self.run.raw_events_seen += 1
        event_type = event.get("event")

        if event_type == "config_loaded":
            self.run.call_id = event.get("call_id")
            self.run.starting_state = event.get("starting_state")
            self.run.current_state = event.get("starting_state")
            first_message = event.get("first_message") or ""
            if first_message:
                self.run.first_message = first_message
                if (
                    not self.run.assistant_messages
                    or self.run.assistant_messages[-1] != first_message.strip()
                ):
                    self.run.add_assistant(first_message)

        elif event_type == "stream_start":
            self.run._stream_chunks = []

        elif event_type == "stream_chunk":
            self.run._stream_chunks.append(event.get("text", ""))

        elif event_type == "stream_end":
            if self.run._stream_chunks:
                self.run.add_assistant("".join(self.run._stream_chunks))
                self.run._stream_chunks = []

        elif event_type == "tool_calls":
            for tool_call in event.get("tool_calls", []):
                args = parse_json_maybe(tool_call.get("arguments", ""))
                result = parse_json_maybe(tool_call.get("result", ""))
                normalized = {
                    "name": tool_call.get("name"),
                    "arguments": args,
                    "result": result,
                }
                self.run.tool_calls.append(normalized)
                summary = summarize_tool_result(result)
                self.run.add_timeline(
                    "tool",
                    "Tool",
                    f"{tool_call.get('name')} args={compact_json(args)} result={summary}",
                )

        elif event_type == "state_changed":
            self.run.current_state = event.get("state")
            self.run.add_timeline("state", "State", self.run.current_state or "")

        elif event_type == "context":
            self.run.context = event
            self.run.current_state = (
                event.get("current_state") or self.run.current_state
            )
            self.run.add_timeline(
                "system",
                "Context",
                f"Captured context snapshot at state {self.run.current_state}",
            )

        elif event_type == "error":
            self.run.error = event.get("message", "Unknown backend error")
            self.run.add_timeline("error", "Error", self.run.error)

        elif event_type == "parse_error":
            self.run.add_timeline("error", "Parse", event.get("message", ""))

        await self.reporter.write()

    async def close(self) -> None:
        if self.proc and self.proc.returncode is None:
            try:
                await self.send({"command": "shutdown"})
                await self.wait_until(
                    predicate=None, timeout=5, target_events={"shutdown_ack"}
                )
            except Exception:
                pass
            if self.proc.returncode is None:
                self.proc.terminate()
                try:
                    await asyncio.wait_for(self.proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    self.proc.kill()
        for task in (self.stdout_task, self.stderr_task):
            if task:
                task.cancel()


def find_tool_call(
    run: ScenarioRun,
    *,
    name: str,
    arg_key: str | None = None,
    arg_value: str | None = None,
    start_index: int = 0,
) -> dict[str, Any] | None:
    for tool_call in run.tool_calls[start_index:]:
        if tool_call.get("name") != name:
            continue
        args = tool_call.get("arguments")
        if arg_key is not None:
            if not isinstance(args, dict):
                continue
            if args.get(arg_key) != arg_value:
                continue
        return tool_call
    return None


def latest_assistant_since(run: ScenarioRun, start_index: int) -> str | None:
    messages = run.assistant_messages[start_index:]
    return messages[-1] if messages else None


def latest_assistant_matching_since(
    run: ScenarioRun, start_index: int, predicate: Callable[[str], bool]
) -> str | None:
    matches = [
        message
        for message in run.assistant_messages[start_index:]
        if predicate(message)
    ]
    return matches[-1] if matches else None


def final_context_consumer_id(run: ScenarioRun) -> str | None:
    if not run.context:
        return None
    dynamic_vars = run.context.get("dynamic_vars") or {}
    user_details = dynamic_vars.get("user_details") or {}
    return user_details.get("consumer_id")


def final_context_prompt(run: ScenarioRun) -> str:
    if not run.context:
        return ""
    messages = run.context.get("messages") or []
    if not messages:
        return ""
    last = messages[-1]
    return str(last.get("content") or "")


async def load_session(client: BackendClient, run: ScenarioRun) -> None:
    await client.send(
        {
            "command": "load_config",
            "to_number": TO_NUMBER,
            "from_number": run.spec.from_number,
            "call_direction": "inbound",
        }
    )
    await client.wait_until(
        lambda current: bool(current.call_id),
        timeout=120,
        target_events={"config_loaded", "error"},
    )


async def scenario_1(run: ScenarioRun, reporter: ReportWriter) -> None:
    client = BackendClient(run, reporter)
    run.status = "running"
    await reporter.write()
    try:
        await client.start()
        await load_session(client, run)

        greeting = run.first_message.lower()
        run.add_check(
            "Greeting stays on phone lookup",
            "reference number" not in greeting,
            "Greeting should ask for phone number and not proactively mention reference number.",
            run.first_message,
        )

        assistant_idx = len(run.assistant_messages)
        await client.send_message("I have a reference number")
        await client.wait_until(
            lambda current: len(current.assistant_messages) > assistant_idx,
            timeout=60,
        )
        response = latest_assistant_since(run, assistant_idx) or ""
        run.add_check(
            "Reactive offer is accepted",
            "reference number" in response.lower(),
            "After the user says they have a reference number, the agent should ask for it.",
            response,
        )

        tool_idx = len(run.tool_calls)
        await client.send_message(REFERENCE_NUMBER)
        await client.wait_until(
            lambda current: find_tool_call(
                current,
                name="get_details_from_contact",
                arg_key="reference_number",
                arg_value=REFERENCE_NUMBER,
                start_index=tool_idx,
            )
            is not None,
            timeout=90,
        )
        await client.drain_until_idle()
        await client.get_context()

        lookup_tool = find_tool_call(
            run,
            name="get_details_from_contact",
            arg_key="reference_number",
            arg_value=REFERENCE_NUMBER,
            start_index=tool_idx,
        )
        run.add_check(
            "Lookup uses reference_number parameter",
            lookup_tool is not None,
            "The successful lookup should call get_details_from_contact with reference_number=70360256.",
            compact_json(lookup_tool["arguments"])
            if lookup_tool
            else "No matching tool call.",
        )
        run.add_check(
            "Correct consumer was loaded",
            final_context_consumer_id(run) == EXPECTED_CONSUMER_ID,
            "The loaded user_details.consumer_id should be 70360256.",
            str(final_context_consumer_id(run)),
        )
        run.add_check(
            "Lookup exits s1 into name verification",
            run.current_state == EXPECTED_STATE,
            f"After successful lookup, the call should move into {EXPECTED_STATE}.",
            str(run.current_state),
        )
        run.add_check(
            "Post-lookup prompt is name verification",
            "full name" in final_context_prompt(run).lower(),
            "The next assistant prompt should ask for the consumer's full name.",
            final_context_prompt(run),
        )

    except Exception as exc:
        run.error = str(exc)
        run.add_timeline("error", "Runner", run.error)
    finally:
        await client.close()
        run.status = "complete"
        run.verdict = "fail" if run.has_failed() else "pass"
        await reporter.write()


async def scenario_2(run: ScenarioRun, reporter: ReportWriter) -> None:
    client = BackendClient(run, reporter)
    run.status = "running"
    await reporter.write()
    try:
        await client.start()
        await load_session(client, run)

        greeting = run.first_message.lower()
        run.add_check(
            "Greeting stays on phone lookup",
            "reference number" not in greeting,
            "Greeting should ask for phone number and not proactively mention reference number.",
            run.first_message,
        )

        assistant_idx = len(run.assistant_messages)
        tool_idx = len(run.tool_calls)
        await client.send_message("1112223333")
        await client.wait_until(
            lambda current: find_tool_call(
                current,
                name="get_details_from_contact",
                arg_key="phone",
                arg_value="1112223333",
                start_index=tool_idx,
            )
            is not None,
            timeout=60,
        )
        await client.wait_until(
            lambda current: latest_assistant_matching_since(
                current, assistant_idx, lambda text: "correct number" in text.lower()
            )
            is not None,
            timeout=60,
        )
        phone_response = (
            latest_assistant_matching_since(
                run, assistant_idx, lambda text: "correct number" in text.lower()
            )
            or ""
        )
        run.add_check(
            "Incorrect phone is treated as phone lookup",
            find_tool_call(
                run,
                name="get_details_from_contact",
                arg_key="phone",
                arg_value="1112223333",
                start_index=tool_idx,
            )
            is not None,
            "The first failed lookup should use the phone parameter with 1112223333.",
            phone_response,
        )
        run.add_check(
            "Phone failure triggers confirmation",
            "correct number" in phone_response.lower(),
            "After an empty phone lookup, the agent should echo the number back and ask if it was correct.",
            phone_response,
        )

        assistant_idx = len(run.assistant_messages)
        await client.send_message("yes")
        await client.wait_until(
            lambda current: latest_assistant_matching_since(
                current,
                assistant_idx,
                lambda text: "social security number" in text.lower(),
            )
            is not None,
            timeout=60,
        )
        ssn_response = (
            latest_assistant_matching_since(
                run,
                assistant_idx,
                lambda text: "social security number" in text.lower(),
            )
            or ""
        )
        run.add_check(
            "Confirmed bad phone leads to SSN offer",
            "social security number" in ssn_response.lower()
            and "reference number" not in ssn_response.lower(),
            "After the phone is confirmed correct, the agent should offer SSN and still not proactively mention reference number.",
            ssn_response,
        )

        assistant_idx = len(run.assistant_messages)
        await client.send_message("I have a reference number")
        await client.wait_until(
            lambda current: latest_assistant_matching_since(
                current,
                assistant_idx,
                lambda text: "reference number" in text.lower()
                and "social security number" not in text.lower(),
            )
            is not None,
            timeout=60,
        )
        reference_prompt = (
            latest_assistant_matching_since(
                run,
                assistant_idx,
                lambda text: "reference number" in text.lower()
                and "social security number" not in text.lower(),
            )
            or ""
        )
        run.add_check(
            "Reference number is accepted mid-flow",
            "reference number" in reference_prompt.lower(),
            "When the user volunteers a reference number after the SSN offer, the agent should ask for it.",
            reference_prompt,
        )

        tool_idx = len(run.tool_calls)
        await client.send_message(REFERENCE_NUMBER)
        await client.wait_until(
            lambda current: find_tool_call(
                current,
                name="get_details_from_contact",
                arg_key="reference_number",
                arg_value=REFERENCE_NUMBER,
                start_index=tool_idx,
            )
            is not None,
            timeout=90,
        )
        await client.drain_until_idle()
        await client.get_context()

        run.add_check(
            "Mid-flow lookup uses reference_number parameter",
            find_tool_call(
                run,
                name="get_details_from_contact",
                arg_key="reference_number",
                arg_value=REFERENCE_NUMBER,
                start_index=tool_idx,
            )
            is not None,
            "The final successful lookup should use reference_number=70360256.",
            str(
                find_tool_call(
                    run,
                    name="get_details_from_contact",
                    arg_key="reference_number",
                    arg_value=REFERENCE_NUMBER,
                    start_index=tool_idx,
                )
            ),
        )
        run.add_check(
            "Correct consumer was loaded",
            final_context_consumer_id(run) == EXPECTED_CONSUMER_ID,
            "The loaded user_details.consumer_id should be 70360256.",
            str(final_context_consumer_id(run)),
        )
        run.add_check(
            "Lookup exits s1 into name verification",
            run.current_state == EXPECTED_STATE,
            f"After successful lookup, the call should move into {EXPECTED_STATE}.",
            str(run.current_state),
        )

    except Exception as exc:
        run.error = str(exc)
        run.add_timeline("error", "Runner", run.error)
    finally:
        await client.close()
        run.status = "complete"
        run.verdict = "fail" if run.has_failed() else "pass"
        await reporter.write()


async def scenario_3(run: ScenarioRun, reporter: ReportWriter) -> None:
    client = BackendClient(run, reporter)
    run.status = "running"
    await reporter.write()
    try:
        await client.start()
        await load_session(client, run)

        greeting = run.first_message.lower()
        run.add_check(
            "Greeting stays on phone lookup",
            "reference number" not in greeting,
            "Greeting should ask for phone number and not proactively mention reference number.",
            run.first_message,
        )

        assistant_idx = len(run.assistant_messages)
        tool_idx = len(run.tool_calls)
        await client.send_message(f"My reference number is {REFERENCE_NUMBER}")
        await client.wait_until(
            lambda current: find_tool_call(
                current,
                name="get_details_from_contact",
                arg_key="reference_number",
                arg_value=REFERENCE_NUMBER,
                start_index=tool_idx,
            )
            is not None,
            timeout=90,
        )
        await client.drain_until_idle()
        await client.get_context()

        extra_prompt = " | ".join(run.assistant_messages[assistant_idx:])
        run.add_check(
            "Directly provided reference number is used immediately",
            "what's the reference number" not in extra_prompt.lower()
            and "what is the reference number" not in extra_prompt.lower()
            and "could you provide the reference number" not in extra_prompt.lower(),
            "When the first user utterance already includes the reference number, the agent should not ask for it again.",
            extra_prompt or "No extra assistant prompt before lookup.",
        )
        run.add_check(
            "Direct lookup uses reference_number parameter",
            find_tool_call(
                run,
                name="get_details_from_contact",
                arg_key="reference_number",
                arg_value=REFERENCE_NUMBER,
                start_index=tool_idx,
            )
            is not None,
            "The direct labeled utterance should trigger get_details_from_contact with reference_number=70360256.",
            str(
                find_tool_call(
                    run,
                    name="get_details_from_contact",
                    arg_key="reference_number",
                    arg_value=REFERENCE_NUMBER,
                    start_index=tool_idx,
                )
            ),
        )
        run.add_check(
            "Correct consumer was loaded",
            final_context_consumer_id(run) == EXPECTED_CONSUMER_ID,
            "The loaded user_details.consumer_id should be 70360256.",
            str(final_context_consumer_id(run)),
        )
        run.add_check(
            "Lookup exits s1 into name verification",
            run.current_state == EXPECTED_STATE,
            f"After successful lookup, the call should move into {EXPECTED_STATE}.",
            str(run.current_state),
        )

    except Exception as exc:
        run.error = str(exc)
        run.add_timeline("error", "Runner", run.error)
    finally:
        await client.close()
        run.status = "complete"
        run.verdict = "fail" if run.has_failed() else "pass"
        await reporter.write()


async def main() -> None:
    scenarios = [
        ScenarioRun(
            ScenarioSpec(
                key="scenario-1",
                title="Reference Number Offered First",
                description="User says they have a reference number, then supplies it when asked.",
                from_number="9998887777",
                expected=[
                    "Greeting should still ask for phone number and should not proactively mention reference number.",
                    "After the user says they have a reference number, the agent should ask for it.",
                    "Lookup should use reference_number=70360256 and resolve KELSEY HOWE.",
                    f"Call should leave s1 and land in {EXPECTED_STATE}.",
                ],
            )
        ),
        ScenarioRun(
            ScenarioSpec(
                key="scenario-2",
                title="Bad Phone Then Reference Number",
                description="User gives a wrong phone number, confirms it, gets the SSN offer, then switches to a reference number.",
                from_number="9998886666",
                expected=[
                    "Greeting should stay on phone-number collection.",
                    "Wrong phone number should be looked up as phone, then echoed for confirmation.",
                    "After confirmation, the agent should offer SSN without proactively mentioning reference number.",
                    "When the user then volunteers a reference number, the agent should accept it and resolve KELSEY HOWE.",
                ],
            )
        ),
        ScenarioRun(
            ScenarioSpec(
                key="scenario-3",
                title="Reference Number Provided Inline",
                description="User replies to the greeting with a fully labeled reference number in the same utterance.",
                from_number="9998885555",
                expected=[
                    "Greeting should not proactively mention reference number.",
                    "The direct labeled reference number should be used immediately without asking for it again.",
                    "Lookup should use reference_number=70360256 and resolve KELSEY HOWE.",
                    f"Call should leave s1 and land in {EXPECTED_STATE}.",
                ],
            )
        ),
    ]

    state: dict[str, Any] = {
        "status": "running",
        "started_at": now_str(),
        "updated_at": now_str(),
        "scenarios": scenarios,
    }
    reporter = ReportWriter(state)
    await reporter.write()

    await asyncio.gather(
        scenario_1(scenarios[0], reporter),
        scenario_2(scenarios[1], reporter),
        scenario_3(scenarios[2], reporter),
    )

    state["status"] = "complete"
    state["finished_at"] = now_str()
    await reporter.write()

    print(str(REPORT_PATH))
    print(str(DATA_PATH))


if __name__ == "__main__":
    asyncio.run(main())
