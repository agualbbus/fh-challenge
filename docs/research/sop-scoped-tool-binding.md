# Analysis — Load Agent Tools Based on Active SOP

## Context

The Watchtower agent (`app/worker/agent.py:225–230`) binds **all 15 tools** from `app/tools/tools.py` to every `create_agent` call, regardless of which SOP is active. But the SOP is already chosen deterministically before the agent runs: `sops.task_for_milestone(milestone)` (`app/worker/sops.py:21–35`) maps `on_route_to_delivery → delivery_eta_checkpoint` and `at_delivery|delivered|pod_collected → confirm_delivery`. The agent therefore re-derives, on every turn, a tool-selection constraint that the SOP has already locked in.

Question from the user: **can we just load the right tools based on the SOP loaded?** Yes — and it's the highest-leverage, lowest-risk rule-based narrowing available.

## What each SOP actually uses

Cross-referencing `docs/SOPs/*` (or the inline SOP text rendered into the prompt) with `app/tools/tools.py`:

**`delivery_eta_checkpoint` SOP** needs:
- `send_sms`, `send_slack_message`
- `update_eta`, `validate_eta`
- `create_timer` (only `eta_followup`), `cancel_timers`
- `update_load_state` (only `at_delivery` transition — driver-says-arrived branch)
- `get_load_info`, `get_appointment_time`
- `create_issue`, `create_task` (missing_load_info, manual_followup)

**`confirm_delivery` SOP** needs:
- `send_sms`, `send_slack_message`
- `check_attachment`, `forward_email`
- `update_load_state` (`at_delivery`, `delivered`, `pod_collected`)
- `create_timer` (`pod_followup`, `delivery_status_followup`, `attachment_clarification`), `cancel_timers`, `cancel_timer`
- `create_task` (`pod_review`, `lumper_review`), `create_issue`
- `get_load_info`

**Tools never bound** under either SOP today: none — but the *overlap* is small. ETA SOP doesn't need `check_attachment` / `forward_email` / POD-state transitions; confirm-delivery SOP doesn't need `update_eta` / `validate_eta` / `get_appointment_time`.

## Proposed shape (constrain, don't bypass)

Introduce a single helper, e.g. `tools_for_sop(sop_section: SopSection) -> list[BaseTool]`, called from `build_agent` where `ALL_TOOLS` is currently passed to `create_agent`. The agent still reasons over text; it just can't pick a tool the SOP forbids.

```python
# app/worker/agent.py (build_agent, ~line 225)
tools = tools_for_sop(state.sop_section)
agent = create_agent(model=llm, tools=tools, prompt=system_prompt)
```

`tools_for_sop` lives next to `sops.task_for_milestone` (`app/worker/sops.py`), so the SOP definition and its tool surface stay co-located.

## Why this is safe

- **No behaviour change on the happy path.** Every fixture's *expected* tool calls are already a subset of the SOP-permitted set.
- **No bypass.** The LLM still chooses inside the narrowed set; phrasing variance still handled.
- **Reversible.** Roll back = pass `ALL_TOOLS` again.
- **No state/schema changes.** No checkpoint migration, no SOP YAML edits, no API contract change.

## Expected payoff

- Smaller prompt → fewer tokens, faster turns.
- Eliminates a class of wrong-tool eval failures (ETA tool picked during confirm-delivery, POD tool picked during ETA checkpoint, etc.).
- Makes `app/worker/sops.py` the single source of truth for "what's in scope for this SOP" — currently that truth is spread across the SOP text rendered into the prompt and the agent's reasoning.

## Out of scope

- Narrowing `Literal` enums inside tool schemas (e.g. restricting `update_load_state.target_state` further by milestone) — useful follow-up, separate change.
- Filtering by customer profile (`notify_slack`, `lumper.mode`) — separate change; touches profile semantics.
- Full LLM bypass for high-confidence cases (broker noop already does this; no new bypasses proposed here).

## Verification (when implemented)

- `uv run pytest`
- `uv run python evals/run_evals.py` — confirm no regression on `3b`, `3c`, `3d`, `3f`, `3h`, `3j`, `3k`.
- Inspect one ETA-event trace and one delivery-confirm trace in LangSmith: tool list should be the SOP-scoped subset.
