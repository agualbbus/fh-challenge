# Live-Mode SOP Prompt Fix — Eval Report

**Date:** 2026-05-24
**Branch:** main
**Mode:** `MODEL_MODE=live` (ChatOpenRouter)
**Plan:** [`~/.claude/plans/immutable-hopping-pebble.md`](../../../.claude/plans/immutable-hopping-pebble.md) (local)

## Result

All four allow-listed eval cases pass under the live LLM.

| Case | Before | After |
| --- | --- | --- |
| 3b_load_question_found | PASS | PASS |
| 3c_load_question_missing | PASS | PASS |
| 3d_truck_broken | **FAIL** — forbidden `create_task` | **PASS** |
| 3k_broker_email_ignore | PASS | PASS |

## Problem

`build_system_prompt` in `app/worker/agent.py` hard-coded the SOP section to
`load_information_question` for every event. For the 3d truck-breakdown case
the live LLM therefore never saw the **Operational Issue** branch of the SOP
and improvised — it called `send_sms`, `create_issue`, `send_slack_message`,
`create_task` (forbidden), and `create_timer` (5 tools, 3 model hops, 25s).
The prompt also explicitly surfaced `Missing load info policy: create_task=true`,
which actively pushed the model toward the forbidden call.

The three other cases passed only by coincidence: 3b and 3c are
load-information branches that happen to match the hard-coded section, and 3k
is short-circuited by `route_event` before the agent runs.

LangSmith trace of the failing run:
`019e5c3d-577c-76e2-99a5-46630a286bca`.

## Fix

Backlog item [`docs/BACKLOG.md:24`](../BACKLOG.md) → "Load all sections of the
active task's SOP into the system prompt […] letting the agent pick the branch".

### Prompt — `app/worker/agent.py`

- Replaced the single-section slice with the full active-task SOP via the new
  `get_sop_document(task_type)` helper in `app/worker/sops.py`.
- Dropped the hand-picked `Missing load info policy: …` line; now dumps the
  full `CustomerProfile` (escalation, geofence, eta_followup, missing_load_info,
  pod, lumper, first_arrival_message_key) as JSON. Branch-relevance is the
  agent's job, not the prompt builder's.
- Added explicit routing rules ("read the Event Routing section first", "do
  not call tools the branch does not authorize").
- Asked the agent to end its final message with `SOP_BRANCH: <branch_key>` /
  `RATIONALE: <one line>`. `_extract_sop_branch` parses this and populates
  `AgentDecision.sop_branch` for trace observability (rubric requirement).

### Tool schemas — `app/tools/tools.py`

The first re-run surfaced a second class of failure: the LLM invented
`task_type='missing_information'` and `issue_type='truck_breakdown'`, which
the fixtures (and `challenge-specs/assets/tools.md`) reject. Tool argument
types were unconstrained `str`. Replaced with `Literal[…]` aliases sourced
verbatim from the spec:

- `TaskType` — `missing_load_info | pod_review | lumper_review | manual_followup | other`
- `IssueType` — `equipment_failure | delivery_delay | facility_problem | other`
- `SlackAudience` — `internal | broker | customer`
- `LoadMilestone` — `on_route_to_delivery | at_delivery | delivered | pod_collected`
- `EtaTarget` — `delivery`
- `TimerType` — `eta_followup | pod_followup | delivery_status_followup | attachment_clarification`
- `get_appointment_time.stop_type` — `pickup | delivery`

These flow into the LangChain tool schema, which OpenRouter validates.

### SOP wording — `app/sops/on_route_to_delivery_eta_checkpoint.md`

Fixtures assert `send_sms` content `contains "checking"` (3c) and `"review"`
(3d). The SOP previously paraphrased ("follow the missing-information
workflow" / "acknowledge briefly that the team will review"); the live LLM
freely rephrased to "looking into it" / "follow up". Bolded the literal
words in the two relevant steps to anchor model output to the fixture
contract.

### Docs

- `docs/BACKLOG.md` — ticked the backlog line.
- `app/worker/CLAUDE.md` — updated the "SOP prompt slice" workaround row to
  describe the new full-document behavior.

## Verification

LangSmith trace of the fixed 3d run:
`019e5cb5-8c82-7151-8dca-1c9e70a44744`.

```
LangGraph (chain) [13.67s]
├── __start__ (chain) [3ms]
│   └── select_branch (chain) [0ms]
└── event (chain) [13.39s]
    └── _invoke_agent (chain) [13.39s]
        └── LangGraph (chain) [12.31s]
            ├── model (chain) [8.11s]   ← ChatOpenRouter
            ├── model (chain) [3.78s]   ← ChatOpenRouter
            ├── tools → send_sms
            └── tools → create_issue
```

Compared to the failing trace: 2 model hops instead of 3, 13s instead of 25s,
exactly the two expected tool calls, no forbidden tools.

### Reproducing

Live evals are not idempotent. Two stores hold state across runs:

1. **LangGraph Postgres checkpoints** — fixed `thread_id = load-eval-{case_id}`
   accumulates `tool_calls` across runs.
2. **ElasticMQ FIFO dedup** — `dedup_id_for_seed = seed-{load_id}` and
   `dedup_id_for_event = event_id` silently drop reposts within the FIFO
   dedup window (~5 min).

A clean re-run requires both:

```bash
docker compose exec postgresql psql -U watchtower -d watchtower \
  -c "DELETE FROM checkpoints WHERE thread_id LIKE 'load-eval-%';
      DELETE FROM checkpoint_blobs WHERE thread_id LIKE 'load-eval-%';
      DELETE FROM checkpoint_writes WHERE thread_id LIKE 'load-eval-%';"
docker compose restart elasticmq
```

Then with `MODEL_MODE=live`, `OPENROUTER_API_KEY`, `LANGSMITH_TRACING=true`,
`LANGSMITH_PROJECT=fh-dev` set:

```bash
uv run uvicorn app.api.main:app --reload --port 8000   # terminal 1
uv run python -m app.worker                            # terminal 2 (no reload)
uv run python -m evals.run_evals                       # terminal 3
```

Worker has no auto-reload — restart it after changes to `app/worker/*` or
`app/tools/*`. SOP markdown is read fresh per request, no restart needed.

## Files Touched

| File | Change |
| --- | --- |
| `app/worker/sops.py` | Added `get_sop_document(task_type)`. |
| `app/worker/agent.py` | Branch-aware full-SOP prompt, full profile dump, `SOP_BRANCH:` parsing. |
| `app/tools/tools.py` | `Literal[…]` enums on six tool argument fields. |
| `app/sops/on_route_to_delivery_eta_checkpoint.md` | Bolded "checking" / "review" wording. |
| `app/worker/CLAUDE.md` | Refreshed the SOP-prompt workaround row. |
| `docs/BACKLOG.md` | Ticked the SOP-prompt backlog item. |
| `evals/EVAL_REPORT.md` | Regenerated by `run_evals.py`. |

## Follow-Ups (Out of Scope)

- `build_system_prompt` is a single 30-line f-string — worth splitting into
  named sections joined with `"\n\n"` once a third branch is added.
- `_extract_sop_branch`'s `AIMessage.content` coercion ladder could use
  `msg.text()` instead.
- Add a `make eval-reset` target wrapping the Postgres + ElasticMQ purge so
  the dedup gotcha doesn't bite again.
- Generate per-run `load_id` suffixes in `evals/run_evals.py` to remove the
  dedup problem entirely.
- Phase 4+ fixtures (3f, 3h, 3i, 3j) — add to `MOCK_CASES` and verify the
  new branch-aware prompt handles ETA, tracking, arrival, and POD branches
  too. Trace traces for `SOP_BRANCH:` to confirm classification.
