## Prodigal Technologies Change Request

**Description**:
Improves session resume robustness and adds dynamic prompt observability to the ProAgent CLI. Four changes bundled:

1. **Dynamic prompt visibility in StatusBar**: When a state has `dynamic_prompting` configured and a variant condition matches, the status bar now shows `dp:<index> <condition_summary>` (e.g., `dp:0 get_data_result=Success`). The backend evaluates conditions against the original config's `dynamic_prompting` definitions (the orchestrator replaces the live state spec after applying a variant, so the CLI reads from `state.config` instead). Handles both raw dict and Pydantic model forms in `state.config["llm_config"]["states"]` — the config entries become Pydantic objects after `ProAgentLLMConfig(**config["llm_config"])` parses them. Emitted on `config_loaded` and `state_changed` events.

2. **Natural resume with tools enabled**: Previously, the resume continuation path disabled all tools (`_no_tools` override) to prevent multi-turn tool loops from creating a "restart" appearance. This was overly restrictive — tool calls during resume are expected behavior. The override and `try/finally` block have been removed so `state_loop.run()` executes with all tools available, same as a normal turn.

3. **Infer current_state from transcript**: Instead of relying on the explicit `current_state` key in session/chat export files, the backend now infers the current state by scanning the transcript for `transition_to_*` tool calls via `_rebuild_state_timeline_from_transcript()`. Falls back to `llm_config.starting_state` if no transitions are found. The explicit key is kept in exports for visibility but is no longer consumed during load.

4. **Empty call_id fallback**: Changed `session_data.get("call_id", generate_call_id())` to `session_data.get("call_id") or generate_call_id()` for both session and chat export formats, so empty string call IDs also trigger UUID generation.

**Files changed** (7 files, +160/-59):
- `backend.py` — Added `_get_dynamic_prompt_info()` helper (handles both dict and Pydantic state entries), removed tool disabling during resume, inferred state from transcript, fixed call_id fallback, imported `_check_conditions`
- `src/protocol/types.ts` — Added `dynamic_prompt_index` and `dynamic_prompt_condition` optional fields to `ConfigLoadedEvent` and `StateChangedEvent`
- `src/hooks/useChat.ts` — Tracks `dynamicPromptIndex`/`dynamicPromptCondition` state, updated on config load and state changes
- `src/components/StatusBar.tsx` — Renders `dp:<index> <condition>` segment when active
- `src/components/ChatView.tsx` — Passes dynamic prompt props to StatusBar
- `src/App.tsx` — Wires dynamic prompt state from chat hook to ChatView
- `CLAUDE.md` — Added constraint: never modify the agent-orchestrator codebase

**Justification**:
- **Dynamic prompt visibility**: Operators testing configs with dynamic prompting had no way to see which variant was active or why. This is critical for prompt debugging and QA — previously required reading backend logs.
- **Natural resume**: Disabling tools during resume prevented legitimate tool calls (e.g., data lookups, state transitions) from executing on the first turn, causing the conversation to diverge from what a live call would produce. This was reported as the first tool call after resume not appearing in the UI.
- **State inference**: Explicit `current_state` in exports could drift out of sync with what the transcript actually shows (especially after `resume_from` slicing). Inferring from tool calls is authoritative and survives manual transcript edits.
- **Call ID fix**: Empty string call IDs passed Python's `dict.get()` default check, resulting in conversations with no identifier.

**Type of Change**:
Standard — Low-risk improvements to the CLI development tool. No changes to the agent_orchestrator codebase.

**Impact Assessment**:
- **ProAgent CLI** (`cli/`): 7 files modified. Resume behavior changes are the highest-risk item — tool calls are now allowed during resume continuation, which could produce additional LLM calls on the first turn.
- **Backend protocol**: Two events (`config_loaded`, `state_changed`) gain optional fields — fully backward-compatible.
- **No impact** on production systems, customer-facing services, or agent_orchestrator core.

**Rollback Procedure**: Revert to previous release version/commit
1. `git revert <commit-sha>` to revert the commit
2. `npm run build` to rebuild
3. Verify CLI resumes sessions normally and StatusBar renders without errors

**Asana Task Link**:

## Testing & Security

**Testing Performed**:
- Build verification: `npm run build` and `npm run typecheck` pass with zero errors
- Python syntax check: `py_compile.compile('backend.py')` passes
- Manual testing: session resume with `--load-session` flag
- Manual testing: chat export load with `--load-session` + `--config` flag
- Verified dynamic prompt index appears in StatusBar when config has `dynamic_prompting` (both fresh session and transcript load)
- Verified StatusBar shows nothing when no dynamic prompting is configured (no visual noise)
- Verified dynamic prompt detection works with Pydantic model state entries (not just raw dicts)
- Verified state inference matches explicit `current_state` for existing exports
- Verified empty string call_id generates a UUID

**Security Considerations(if-any)**:
No security implications. `_check_conditions` import from orchestrator's prompts module is a read-only condition evaluator — no new network, authentication, or data handling changes. No OWASP Top 10 concerns.

## Checklist
- [ ] Peer code review completed
- [ ] Dev/QA testing performed
- [ ] Documentation updated - if applicable (Asana, code comments, Notion, git comments)
