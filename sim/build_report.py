"""
Build a consolidated markdown report from the three simulator transcript files.

Renders user messages, agent messages, and tool calls (with arguments + results)
inline so the report reads as a transcript with full role context.
"""

from __future__ import annotations

import json
import os
import textwrap
from typing import Any, Dict, List

RUN_DIR = "/Users/vansh/Developer/agent-orchestrator/cli/sim/runs/kit_lam"
CALLS = [
    ("Call 1 — 3 Monthly Installments", f"{RUN_DIR}/sim_call_1_transcript.json"),
    ("Call 2 — 2 Parts with $500 Down", f"{RUN_DIR}/sim_call_2_transcript.json"),
    ("Call 3 — 5 Weekly + 3 Monthly", f"{RUN_DIR}/sim_call_3_transcript.json"),
]

OUT_PATH = "/Users/vansh/Developer/agent-orchestrator/cli/sim/runs/kit_lam_consolidated_report.md"


def _truncate(s: str, n: int = 600) -> str:
    s = s.strip()
    if len(s) <= n:
        return s
    return s[:n] + f"… [{len(s) - n} more chars]"


def _format_args(arg_str: str) -> str:
    try:
        parsed = json.loads(arg_str)
        return json.dumps(parsed, indent=2, ensure_ascii=False)
    except Exception:
        return arg_str


def render_call(label: str, path: str) -> List[str]:
    if not os.path.exists(path):
        return [f"### {label}\n\n_(transcript missing at `{path}`)_\n"]

    with open(path) as f:
        data = json.load(f)

    transcript: List[Dict[str, Any]] = data.get("transcript", [])
    out: List[str] = []
    out.append(f"## {label}")
    out.append("")
    out.append(f"- **Saved transcript:** `{path}`")
    out.append(f"- **Starting state:** `{data.get('starting_state')}`")
    out.append(f"- **Final state:** `{data.get('current_state')}`")
    out.append(f"- **Call ID:** `{data.get('call_id')}`")
    out.append(f"- **Total transcript items:** {len(transcript)}")
    out.append("")
    out.append("### Conversation")
    out.append("")

    user_turn = 0
    agent_turn = 0
    for msg in transcript:
        role = msg.get("role")
        content = (msg.get("content") or "").strip()
        if role == "user":
            user_turn += 1
            if not content:
                continue  # skip the empty greeting trigger
            out.append(f"**[user · turn {user_turn}]** {content}")
            out.append("")
        elif role in ("assistant", "agent"):
            agent_turn += 1
            if content:
                out.append(f"**[agent · turn {agent_turn}]** {content}")
                out.append("")
            tool_calls = msg.get("tool_calls") or []
            for tc in tool_calls:
                fn = tc.get("function") or {}
                name = fn.get("name", "?")
                args = _format_args(fn.get("arguments", "") or "")
                out.append(f"<details><summary>🛠 tool call · `{name}`</summary>")
                out.append("")
                out.append("```json")
                out.append(args)
                out.append("```")
                out.append("</details>")
                out.append("")
        elif role == "tool":
            tc_id = msg.get("tool_call_id", "?")
            result = _truncate(msg.get("content") or "", 1000)
            out.append(f"<details><summary>↳ tool result · `{tc_id}`</summary>")
            out.append("")
            out.append("```")
            out.append(result)
            out.append("```")
            out.append("</details>")
            out.append("")

    out.append("---")
    out.append("")
    return out


def main() -> None:
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    parts: List[str] = []
    parts.append("# ProAgent CLI Multi-Subagent Simulation — Consolidated Report")
    parts.append("")
    parts.append(
        textwrap.dedent("""
        Three subagents ran in parallel against the same ProAgent voice config
        (agent number `7066226252`), each driving a separate conversation as
        consumer **KIT LAM** (account `70360219`, full SSN `639992044`,
        DOB `1994-06-17`). Each subagent owned its own backend daemon and
        socket, talking turn-by-turn through `cli/sim/say.py`.

        ## Negotiation goals

        | Call | Plan attempted |
        |------|----------------|
        | 1    | 3 monthly installments |
        | 2    | 2 parts with $500 down today + 1 remaining installment |
        | 3    | 5 weekly + 3 monthly installments (hybrid cadence) |

        ## Outcomes (high-level)

        | Call | RPC | Plan negotiated | Card setup | Final state |
        |------|-----|-----------------|------------|-------------|
        | 1 — 3 monthly       | ✅ via SSN | ✅ 3 × $3,497.65 (Apr 30, May 30, Jun 30 2026) | ❌ blocked: active plan conflict (Call 2 booked first) → transferred | `s6_payment_on_call` |
        | 2 — $500 down + 1   | ✅ via SSN | ✅ $500 today + $9,992.96 on May 30 2026 | ✅ `payment_plan_id: plan_pyx35nxxby` | `s6_payment_on_call` |
        | 3 — 5w + 3m hybrid  | ✅ via SSN | ✅ 8 × $1,311.62 (5 weekly then 3 monthly) | ❌ blocked: active plan conflict → transferred | `s6_payment_on_call` |

        > Only one call could complete card setup because the account locks to a single
        > active payment plan. Subagent 2 won the booking race; the other two had their
        > negotiated plans saved via `set_accepted_payment_plan` but `setup_payment_plan_via_card`
        > rejected the charge. Real outstanding balance per the agent: **$10,492.96**.

        ---
    """).strip()
    )
    parts.append("")

    for label, path in CALLS:
        parts.extend(render_call(label, path))

    with open(OUT_PATH, "w") as f:
        f.write("\n".join(parts))

    print(f"Wrote {OUT_PATH} ({os.path.getsize(OUT_PATH)} bytes)")


if __name__ == "__main__":
    main()
