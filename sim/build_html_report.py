"""
Render the three call transcripts as a terminal-themed HTML report.

Each call is shown as a fake CLI window using the actual ProAgent CLI palette
and glyphs (theme.ts + MessageBubble.tsx + ToolCallDisplay.tsx + StatusBar.tsx).

Layout:
- Top toolbar with column-count picker (1 / 2 / 3 / 4) and theme summary
- Call windows arranged in a CSS grid with the picked number of columns
- Each window has a macOS-style title bar, status bar, scrollable content,
  and an input bar mimicking the CLI footer

Self-contained: inline CSS + a tiny vanilla JS handler for the picker.
"""

from __future__ import annotations

import html
import json
import os
from typing import Any, Dict, List

RUN_DIR = "/Users/vansh/Developer/agent-orchestrator/cli/sim/runs/kit_lam"

CALLS = [
    {
        "label": "Call 1 — 3 Monthly",
        "subtitle": "subagent_1_three_parts_kit",
        "path": f"{RUN_DIR}/sim_call_1_transcript.json",
        "summary": {
            "RPC": ("✓ via SSN", "ok"),
            "Plan": ("3 × $3,497.65", "ok"),
            "Card": ("✗ active-plan conflict → transferred", "bad"),
        },
    },
    {
        "label": "Call 2 — $500 Down + 1",
        "subtitle": "subagent_2_two_parts_500_down_kit",
        "path": f"{RUN_DIR}/sim_call_2_transcript.json",
        "summary": {
            "RPC": ("✓ via SSN", "ok"),
            "Plan": ("$500 + $9,992.96", "ok"),
            "Card": ("✓ plan_pyx35nxxby", "ok"),
        },
    },
    {
        "label": "Call 3 — 5 Weekly + 3 Monthly",
        "subtitle": "subagent_3_five_weekly_three_monthly_kit",
        "path": f"{RUN_DIR}/sim_call_3_transcript.json",
        "summary": {
            "RPC": ("✓ via SSN", "ok"),
            "Plan": ("8 × $1,311.62", "ok"),
            "Card": ("✗ active-plan conflict → transferred", "bad"),
        },
    },
]

OUT = "/Users/vansh/Developer/agent-orchestrator/cli/sim/runs/kit_lam_consolidated_report.html"

# Glyphs — exact match for cli/src/theme.ts
G = {
    "diamond": "◆",
    "diamondD": "◈",
    "arrow": "▸",
    "bullet": "●",
    "bulletO": "○",
    "prompt": "❯",
    "sep": "│",
    "block": "▌",
    "gear": "⟐",
    "check": "✓",
    "cross": "✗",
    "dot": "·",
    "star": "✦",
    "cursor": "▋",
    "ellipsis": "…",
}

HIGHLIGHT_TOOLS = {"transfer_call", "end_the_call", "execute_code"}


def esc(s: Any) -> str:
    return html.escape(str(s) if s is not None else "", quote=False)


def fmt_args(arg_str: str) -> str:
    try:
        return json.dumps(json.loads(arg_str), indent=2, ensure_ascii=False)
    except Exception:
        return arg_str or ""


def truncate(s: str, n: int = 200) -> str:
    s = s or ""
    if len(s) <= n:
        return s
    return s[:n] + G["ellipsis"]


def render_tool_call(tc: Dict[str, Any]) -> str:
    fn = tc.get("function") or {}
    name = fn.get("name", "?")
    args = fmt_args(fn.get("arguments", "") or "")

    if name in HIGHLIGHT_TOOLS:
        cls = "tool-warning"
    elif name.startswith("transition_to_"):
        cls = "tool-builtin"
    else:
        cls = "tool-accent"

    return (
        f'<div class="tool-box {cls}">'
        f'  <div class="tool-name">{G["star"]} {esc(name)}</div>'
        f'  <details class="tool-section">'
        f'    <summary><span class="tool-label">args</span></summary>'
        f"    <pre>{esc(args)}</pre>"
        f"  </details>"
        f"</div>"
    )


def render_tool_result(msg: Dict[str, Any]) -> str:
    tc_id = msg.get("tool_call_id", "?")
    raw = msg.get("content", "") or ""
    return (
        f'<div class="tool-box tool-result">'
        f'  <div class="tool-name">{G["arrow"]} result <span class="muted">{esc(tc_id)}</span></div>'
        f'  <details class="tool-section">'
        f'    <summary><span class="tool-label">out</span> <span class="muted">{esc(truncate(raw, 120))}</span></summary>'
        f"    <pre>{esc(raw)}</pre>"
        f"  </details>"
        f"</div>"
    )


def render_message(msg: Dict[str, Any]) -> str:
    role = msg.get("role")
    content = (msg.get("content") or "").strip()

    if role == "user":
        if not content:
            return ""
        return (
            f'<div class="bubble user">'
            f'  <div class="bubble-head"><span class="role-user">{G["bullet"]} You</span></div>'
            f'  <div class="bubble-body">{esc(content)}</div>'
            f"</div>"
        )

    if role in ("assistant", "agent"):
        out: List[str] = []
        if content:
            out.append(
                f'<div class="bubble agent">'
                f'  <div class="bubble-head"><span class="role-agent">{G["diamond"]} Assistant</span></div>'
                f'  <div class="bubble-body">{esc(content)}</div>'
                f"</div>"
            )
        for tc in msg.get("tool_calls") or []:
            out.append(render_tool_call(tc))
        return "".join(out)

    if role == "tool":
        return render_tool_result(msg)

    return ""


def render_call_window(call: Dict[str, Any]) -> str:
    path = call["path"]
    if not os.path.exists(path):
        return f'<section class="window"><div class="titlebar"><span class="dots"><i></i><i></i><i></i></span><span class="title">{esc(call["label"])}</span></div><div class="missing">missing transcript: {esc(path)}</div></section>'

    with open(path) as f:
        data = json.load(f)
    transcript: List[Dict[str, Any]] = data.get("transcript", [])

    starting = data.get("starting_state") or "—"
    final = data.get("current_state") or "—"
    cid = data.get("call_id") or "—"

    # Build a status bar that mirrors StatusBar.tsx
    status_bar = (
        f'<div class="statusbar">'
        f'  <span class="sb primary">{G["diamondD"]} PROAGENT</span>'
        f'  <span class="sb sep">{G["sep"]}</span>'
        f'  <span class="sb warning">{G["arrow"]} {esc(final)}</span>'
        f'  <span class="sb sep">{G["sep"]}</span>'
        f'  <span class="sb muted">call {G["dot"]} {esc(cid)}</span>'
        f'  <span class="sb sep">{G["sep"]}</span>'
        f'  <span class="sb muted">cfg {G["dot"]} remote</span>'
        f"</div>"
    )

    # Outcome chips
    chips = []
    for k, (v, kind) in call["summary"].items():
        chips.append(
            f'<span class="chip {kind}"><span class="chip-k">{esc(k)}</span><span class="chip-v">{esc(v)}</span></span>'
        )
    chip_row = '<div class="chip-row">' + "".join(chips) + "</div>"

    # Body messages
    body_parts: List[str] = []
    for msg in transcript:
        rendered = render_message(msg)
        if rendered:
            body_parts.append(rendered)

    # Footer mimicking CLI hints
    footer_hints = [
        ("^E", "export"),
        ("^L", "logs"),
        ("^S", "save"),
        ("^R", "rewind"),
        ("^X", "context"),
        ("^P", "prompt"),
        ("^B", "batch"),
        ("^T", "select text"),
        ("^C", "exit"),
    ]
    sep_dot = f' <span class="muted">{G["dot"]}</span> '
    footer_inner = sep_dot.join(
        f'<span class="hint"><span class="key">{esc(k)}</span> {esc(l)}</span>'
        for k, l in footer_hints
    )

    return (
        f'<section class="window">'
        f'  <div class="titlebar">'
        f'    <span class="dots"><i></i><i></i><i></i></span>'
        f'    <span class="title">{esc(call["label"])}</span>'
        f'    <span class="subtitle">{esc(call["subtitle"])}</span>'
        f"  </div>"
        f"  {status_bar}"
        f"  {chip_row}"
        f'  <div class="meta-row">'
        f'    <span><span class="muted">starting</span> <code>{esc(starting)}</code></span>'
        f'    <span><span class="muted">items</span> <code>{len(transcript)}</code></span>'
        f'    <span><span class="muted">file</span> <code>{esc(os.path.basename(path))}</code></span>'
        f"  </div>"
        f'  <div class="thread">'
        f"    {''.join(body_parts)}"
        f"  </div>"
        f'  <div class="inputbar">'
        f'    <span class="prompt">{G["prompt"]}</span>'
        f'    <span class="placeholder">end of transcript</span>'
        f"  </div>"
        f'  <div class="hints"><span class="muted">{G["bulletO"]}</span> {footer_inner}</div>'
        f"</section>"
    )


CSS = r"""
:root {
  --bg:           #0a0a0a;
  --bg-2:         #111111;
  --panel:        #141414;
  --panel-2:      #1a1a1a;
  --primary:      #3291ff;
  --success:      #62c073;
  --warning:      #f5a623;
  --error:        #ff6066;
  --info:         #51a8ff;
  --accent:       #be79f0;
  --builtin:      #d4a3ff;
  --muted:        #888888;
  --emphasis:     #ededed;
  --border:       #333333;
  --border-soft:  #232323;
  --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}
* { box-sizing: border-box; }
html, body {
  margin: 0;
  padding: 0;
  background: var(--bg);
  color: var(--emphasis);
  font-family: var(--mono);
  font-size: 13px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
a { color: var(--primary); text-decoration: none; }
a:hover { text-decoration: underline; }
code { font-family: var(--mono); background: var(--bg-2); padding: 1px 5px; border-radius: 3px; color: var(--emphasis); }
.muted { color: var(--muted); }

/* ───────── toolbar ───────── */
.toolbar {
  position: sticky;
  top: 0;
  z-index: 5;
  background: rgba(10, 10, 10, 0.92);
  backdrop-filter: blur(6px);
  border-bottom: 1px solid var(--border);
  padding: 14px 22px;
  display: flex;
  align-items: center;
  gap: 18px;
  flex-wrap: wrap;
}
.toolbar h1 {
  margin: 0;
  font-size: 14px;
  color: var(--primary);
  font-weight: 600;
}
.toolbar h1 .star { color: var(--accent); margin-right: 6px; }
.toolbar .meta {
  font-size: 12px;
  color: var(--muted);
}
.toolbar .grow { flex: 1; }
.toolbar .col-picker {
  display: flex;
  align-items: center;
  gap: 8px;
}
.toolbar .col-picker label {
  font-size: 12px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.toolbar .col-picker .btn {
  background: var(--panel);
  color: var(--emphasis);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 10px;
  font-family: var(--mono);
  font-size: 12px;
  cursor: pointer;
  user-select: none;
}
.toolbar .col-picker .btn:hover { border-color: var(--primary); }
.toolbar .col-picker .btn.active {
  background: rgba(50, 145, 255, 0.12);
  border-color: var(--primary);
  color: var(--primary);
}
.toolbar .col-picker input[type=range] {
  accent-color: var(--primary);
}

/* ───────── intro ───────── */
.intro {
  margin: 18px 22px 0;
  padding: 16px 18px;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 8px;
}
.intro p { margin: 4px 0; color: var(--muted); font-size: 12px; }
.intro p strong { color: var(--emphasis); }
.intro table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; }
.intro th, .intro td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border-soft); }
.intro th { color: var(--muted); font-weight: 500; }
.intro td.ok { color: var(--success); }
.intro td.bad { color: var(--error); }

/* ───────── grid ───────── */
.grid {
  --cols: 2;
  display: grid;
  grid-template-columns: repeat(var(--cols), minmax(0, 1fr));
  gap: 18px;
  padding: 18px 22px 40px;
}

/* ───────── window ───────── */
.window {
  display: flex;
  flex-direction: column;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  min-height: 700px;
  max-height: calc(100vh - 60px);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.6);
}
.titlebar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: linear-gradient(180deg, #1a1a1a, #131313);
  border-bottom: 1px solid var(--border);
}
.titlebar .dots { display: inline-flex; gap: 6px; }
.titlebar .dots i {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #3a3a3a;
}
.titlebar .dots i:nth-child(1) { background: #ff5f57; }
.titlebar .dots i:nth-child(2) { background: #febc2e; }
.titlebar .dots i:nth-child(3) { background: #28c840; }
.titlebar .title {
  color: var(--emphasis);
  font-size: 12px;
  font-weight: 600;
}
.titlebar .subtitle {
  color: var(--muted);
  font-size: 11px;
  margin-left: auto;
}
.statusbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0 6px;
  padding: 6px 10px;
  margin: 8px 10px 0;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 11px;
  background: rgba(0,0,0,0.25);
}
.statusbar .sb { white-space: nowrap; }
.statusbar .sep { color: var(--border); }
.statusbar .primary { color: var(--primary); font-weight: 600; }
.statusbar .warning { color: var(--warning); font-weight: 600; }
.statusbar .muted { color: var(--muted); }
.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 10px 0;
}
.chip {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  padding: 3px 8px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 11px;
  background: var(--panel);
}
.chip.ok { border-color: rgba(98,192,115,0.4); }
.chip.bad { border-color: rgba(255,96,102,0.45); }
.chip-k { color: var(--muted); text-transform: uppercase; font-size: 10px; letter-spacing: 0.06em; }
.chip-v { color: var(--emphasis); }
.chip.ok .chip-v { color: var(--success); }
.chip.bad .chip-v { color: var(--error); }
.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  padding: 8px 12px;
  font-size: 11px;
  color: var(--muted);
  border-bottom: 1px solid var(--border-soft);
}
.meta-row code { color: var(--emphasis); font-size: 11px; }

.thread {
  flex: 1 1 auto;
  overflow-y: auto;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
.thread::-webkit-scrollbar { width: 8px; }
.thread::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
.thread::-webkit-scrollbar-track { background: transparent; }

/* bubbles — match MessageBubble.tsx */
.bubble {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.bubble-head { font-weight: 600; font-size: 12px; }
.bubble-body {
  white-space: pre-wrap;
  word-wrap: break-word;
  padding-left: 12px;
  border-left: 2px solid var(--border-soft);
  color: var(--emphasis);
  font-size: 12.5px;
}
.bubble.user .role-user { color: var(--success); }
.bubble.agent .role-agent { color: var(--primary); }

/* tool boxes — match ToolCallDisplay.tsx (rounded box, colored border) */
.tool-box {
  margin-left: 16px;
  padding: 6px 10px;
  border: 1px solid var(--accent);
  border-radius: 6px;
  background: rgba(190,121,240,0.05);
  font-size: 12px;
}
.tool-box.tool-warning {
  border-color: var(--warning);
  background: rgba(245,166,35,0.06);
}
.tool-box.tool-warning .tool-name { color: var(--warning); }
.tool-box.tool-builtin {
  border-color: var(--builtin);
  background: rgba(212,163,255,0.06);
}
.tool-box.tool-builtin .tool-name { color: var(--builtin); }
.tool-box.tool-result {
  border-style: dashed;
  border-color: var(--info);
  background: rgba(81,168,255,0.05);
}
.tool-box.tool-result .tool-name { color: var(--info); }
.tool-name {
  color: var(--accent);
  font-weight: 600;
  margin-bottom: 2px;
}
.tool-section { margin-top: 4px; }
.tool-section > summary {
  cursor: pointer;
  list-style: none;
  color: var(--muted);
  font-size: 11px;
  outline: none;
}
.tool-section > summary::-webkit-details-marker { display: none; }
.tool-section > summary:hover { color: var(--emphasis); }
.tool-label {
  color: var(--muted);
  text-transform: lowercase;
  font-style: italic;
  margin-right: 6px;
}
.tool-section pre {
  margin: 6px 0 0;
  padding: 8px 10px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 4px;
  white-space: pre-wrap;
  word-wrap: break-word;
  max-height: 320px;
  overflow: auto;
  color: var(--emphasis);
  font-size: 11.5px;
}

.inputbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-top: 1px solid var(--border-soft);
  background: var(--panel);
  font-size: 12px;
}
.inputbar .prompt { color: var(--accent); }
.inputbar .placeholder { color: var(--muted); font-style: italic; }
.hints {
  display: flex;
  flex-wrap: wrap;
  gap: 0 6px;
  padding: 6px 12px 10px;
  font-size: 11px;
  color: var(--muted);
  border-top: 1px solid var(--border-soft);
  background: var(--panel-2);
}
.hints .key { color: var(--emphasis); font-weight: 600; }
.hint { white-space: nowrap; }

@media (max-width: 900px) {
  .grid { --cols: 1 !important; }
}
"""


JS = r"""
(() => {
  const grid = document.querySelector('.grid');
  const slider = document.getElementById('col-slider');
  const buttons = document.querySelectorAll('.col-btn');
  const apply = (n) => {
    grid.style.setProperty('--cols', n);
    slider.value = n;
    buttons.forEach(b => b.classList.toggle('active', Number(b.dataset.cols) === Number(n)));
    try { localStorage.setItem('proagent-report-cols', String(n)); } catch (e) {}
  };
  buttons.forEach(b => b.addEventListener('click', () => apply(Number(b.dataset.cols))));
  slider.addEventListener('input', e => apply(Number(e.target.value)));
  let saved = null;
  try { saved = localStorage.getItem('proagent-report-cols'); } catch (e) {}
  apply(saved ? Number(saved) : 2);
})();
"""


def main() -> None:
    parts: List[str] = []
    parts.append("<!doctype html><html><head><meta charset='utf-8'>")
    parts.append("<title>ProAgent CLI · Multi-Subagent Run</title>")
    parts.append(f"<style>{CSS}</style></head><body>")

    # Toolbar with column picker
    parts.append(f"""
    <header class="toolbar">
      <h1><span class="star">{G["star"]}</span> ProAgent CLI · multi-subagent run</h1>
      <span class="meta">3 parallel calls {G["dot"]} consumer KIT LAM {G["dot"]} <code>--to-number 7066226252</code></span>
      <span class="grow"></span>
      <div class="col-picker">
        <label>Panes per row</label>
        <button class="btn col-btn" data-cols="1">1</button>
        <button class="btn col-btn" data-cols="2">2</button>
        <button class="btn col-btn" data-cols="3">3</button>
        <button class="btn col-btn" data-cols="4">4</button>
        <input type="range" id="col-slider" min="1" max="4" step="1" value="2" />
      </div>
    </header>
    """)

    # Intro / outcome summary
    parts.append("""
    <section class="intro">
      <p>Three subagents drove independent ProAgent calls in parallel against the same voice config. Each owned a Python backend daemon (Unix socket per call), reasoning turn-by-turn — no scripted dialogue. Theme & glyphs match the actual CLI (<code>cli/src/theme.ts</code>).</p>
      <p><strong>Persona:</strong> KIT LAM · DOB 1994-06-17 · SSN 639992044 · 5534 Dorchester Ln, Garland TX 75040 · account <code>70360219</code> · balance per agent <strong>$10,492.96</strong></p>
      <p><strong>Card used during processing:</strong> 4111&nbsp;1111&nbsp;1111&nbsp;1111 · CVV 123 · Exp 12/30</p>
      <table>
        <thead><tr><th>Call</th><th>Plan goal</th><th>RPC</th><th>Plan saved</th><th>Card processed</th><th>Final state</th></tr></thead>
        <tbody>
          <tr><td>Call 1</td><td>3 monthly</td><td class="ok">✓ via SSN</td><td class="ok">✓ 3 × $3,497.65</td><td class="bad">✗ active-plan conflict → transferred</td><td><code>s6_payment_on_call</code></td></tr>
          <tr><td>Call 2</td><td>$500 down + 1</td><td class="ok">✓ via SSN</td><td class="ok">✓ $500 + $9,992.96</td><td class="ok">✓ <code>plan_pyx35nxxby</code></td><td><code>s6_payment_on_call</code></td></tr>
          <tr><td>Call 3</td><td>5 weekly + 3 monthly</td><td class="ok">✓ via SSN</td><td class="ok">✓ 8 × $1,311.62</td><td class="bad">✗ active-plan conflict → transferred</td><td><code>s6_payment_on_call</code></td></tr>
        </tbody>
      </table>
    </section>
    """)

    parts.append('<div class="grid">')
    for call in CALLS:
        parts.append(render_call_window(call))
    parts.append("</div>")

    parts.append(f"<script>{JS}</script>")
    parts.append("</body></html>")

    with open(OUT, "w") as f:
        f.write("\n".join(parts))
    print(f"Wrote {OUT} ({os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    main()
