# Evals

Fixture eval harness for the FreightHero Watchtower take-home.

The harness drives fixture cases through the **real HTTP API → SQS → worker →
LangGraph → Postgres** stack and then reads each load's checkpoint to assert
the recorded tool trajectory and final milestone. It does **not** invoke the
graph in-process and there is no read HTTP API.

Run it with:

```bash
uv run python -m evals.run_evals
```

Requires: API (`:8000`), worker, Postgres, and ElasticMQ/SQS all up, with
`MODEL_MODE=mock` so the deterministic fixture LLM
([`../app/worker/mock_model.py`](../app/worker/mock_model.py)) drives tool
calls.

## Files

| File | Role |
| --- | --- |
| [`run_evals.py`](run_evals.py) | Harness entrypoint: seeds loads via `POST /loads`, posts each event, polls the checkpoint, runs assertions, writes `EVAL_REPORT.md`. |
| [`assertions.py`](assertions.py) | Pure assertion helpers: `assert_tool_called`, `assert_tool_forbidden`, `assert_state`, and the aggregator `run_case_assertions`. |
| [`fixtures/test-cases.json`](fixtures/test-cases.json) | Visible challenge scenarios. Each case has `customer_id`, `initial_state`, optional `load_data_patch`, `events`, and `expected` (`required_tool_calls`, `forbidden_tool_calls`, `expected_state`). |
| [`EVAL_REPORT.md`](EVAL_REPORT.md) | Auto-generated PASS/FAIL table; rewritten on every run by `_write_report`. |

Runtime dependencies:

| Module | Relationship |
| --- | --- |
| [`../app/api/routes.py`](../app/api/routes.py) | Write endpoints the harness posts to (`/loads`, `/events/inbound-communication`, `/events/tracking`, `/events/load-update`). |
| [`../app/worker/graph.py`](../app/worker/graph.py) | `query_load_state` reads checkpoint state for assertions. |
| [`../app/worker/checkpointer.py`](../app/worker/checkpointer.py) | `init_checkpointer` opens the `AsyncPostgresSaver`. |
| [`../app/worker/mock_model.py`](../app/worker/mock_model.py) | Deterministic fixture LLM driving tool calls (parallel surface to the live OpenRouter path). |

## Allow-Listed Cases

`run_evals.py` only runs cases listed in the `MOCK_CASES` set. New fixtures are
added explicitly so unverified branches don't silently pollute the report.
Current set:

```python
MOCK_CASES = {
    "3b_load_question_found",
    "3c_load_question_missing",
    "3d_truck_broken",
    "3k_broker_email_ignore",
}
```

Cases in `fixtures/test-cases.json` outside this set are still definitions —
they are exercised once the runtime supports their branch (routing, mock-model
keywords, tools), then added to `MOCK_CASES`.

## End-To-End Flow

```mermaid
sequenceDiagram
    participant Harness as run_evals
    participant API as FastAPI
    participant SQS as SQS_FIFO
    participant Worker as worker
    participant Graph as LangGraph
    participant PG as Postgres
    participant Asserts as assertions

    Harness->>API: POST /loads (seed)
    API->>SQS: publish kind=seed
    API-->>Harness: 202
    loop each event in case
        Harness->>API: POST /events/* (event payload)
        API->>SQS: publish kind=event
        API-->>Harness: 202
    end
    Worker->>SQS: long poll
    Worker->>Graph: ainvoke (seed)
    Graph->>PG: checkpoint milestone, load_data
    Worker->>Graph: ainvoke (event)
    Graph->>Graph: route_event -> mock LLM -> tools
    Graph->>PG: checkpoint tool_calls
    loop until milestone set AND tool count >= expected
        Harness->>PG: query_load_state(load_id)
    end
    Harness->>Asserts: run_case_assertions(state, expected)
    Harness->>Harness: write EVAL_REPORT.md
```

The harness never talks to the worker directly — it only writes through the
HTTP API and reads through the Postgres checkpoint, mirroring how the
challenge rubric will exercise the system.

## Per-Case Pipeline

```mermaid
flowchart TD
    pickCase["pick case from fixtures<br/>filtered by MOCK_CASES"] --> buildSeed["_build_load_seed<br/>apply load_data_patch"]
    buildSeed --> postLoads["POST /loads"]
    postLoads --> postEvents["POST each event<br/>by event_type"]
    postEvents --> wait["_wait_for_tools<br/>poll checkpoint"]
    wait -->|milestone set AND<br/>tool_calls >= min| read["query_load_state"]
    wait -->|timeout 30s| read
    read --> required["required_tool_calls<br/>tool / contains / arguments"]
    read --> forbidden["forbidden_tool_calls"]
    read --> state["expected_state vs milestone"]
    required --> report["row in EVAL_REPORT.md"]
    forbidden --> report
    state --> report
```

Key polling detail: `_wait_for_tools` gates on **both** `milestone` being set
and `len(tool_calls) >= min_count`. Without the milestone check, zero-tool
cases (e.g. `3k_broker_email_ignore`) would read the checkpoint before the
seed message landed and falsely fail the `expected_state` assertion.

## Fixture Shape

```json
{
  "id": "3d_truck_broken",
  "customer_id": "customer_a",
  "initial_state": "on_route_to_delivery",
  "load_data_patch": { "stops[1].reference_numbers.receiver_phone": null },
  "events": [ { "event_type": "inbound_communication", "...": "..." } ],
  "expected": {
    "required_tool_calls": [
      { "tool": "create_issue", "arguments": { "issue_type": "equipment_failure" } },
      { "tool": "send_sms", "contains": "review" }
    ],
    "forbidden_tool_calls": ["create_task", "update_eta", "update_load_state"],
    "expected_state": "on_route_to_delivery"
  }
}
```

- `load_data_patch` keys use dotted paths with `[index]` for arrays, applied
  by `_apply_patch` before the seed POST.
- `required_tool_calls` entries match against the tool name, an optional
  `contains` substring (matched against the stringified call), and an optional
  `arguments` subset.
- `forbidden_tool_calls` is a flat list of tool names that must not appear.
- `expected_state` is the final `milestone` (looked up at top level or under
  `load_state.milestone`).

## Assertions

| Helper | Behavior |
| --- | --- |
| `assert_tool_called(tool, contains?, arguments?)` | Fails if no `tool_calls` entry has the matching tool, or substring/argument subset don't match. |
| `assert_tool_forbidden(tool)` | Fails if any entry uses the forbidden tool. |
| `assert_state(milestone, expected)` | Direct equality on milestone. |
| `run_case_assertions` | Runs all three, collects messages, returns the list of errors (empty list = PASS). |

## Gotchas

- **Run as a module.** `uv run python evals/run_evals.py` fails with
  `ModuleNotFoundError: evals`. Use `uv run python -m evals.run_evals` (or the
  `Makefile` `eval` target). `run_evals.py` also injects the repo root into
  `sys.path` as a defensive fallback.
- **Live stack required.** The harness needs API, worker, Postgres, and
  SQS/ElasticMQ up. Missing the worker presents as the polling loop timing out
  after 30s with no `tool_calls`.
- **`MODEL_MODE=mock` only.** Live OpenRouter responses are nondeterministic
  and will not satisfy the strict tool-call assertions. CI must stay on mock.
- **Adding a fixture is two surfaces minimum.** Update
  [`fixtures/test-cases.json`](fixtures/test-cases.json) **and** the relevant
  runtime path (router in [`../app/worker/agent.py`](../app/worker/agent.py),
  keyword/branch in [`../app/worker/mock_model.py`](../app/worker/mock_model.py),
  any new tools in [`../app/tools/tools.py`](../app/tools/tools.py)) before
  promoting the ID into `MOCK_CASES`.
- **`EVAL_REPORT.md` is generated.** Don't hand-edit; it is rewritten on every
  run.
