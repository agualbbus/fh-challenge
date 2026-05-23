# FreightHero Watchtower — Implementation Plan

A small production-shaped AI operator for two freight workflows: **ETA Checkpoint** and **Confirm Delivery**.

## Stack

| Concern | Choice |
| --- | --- |
| Language / web framework | Python + FastAPI |
| Agent + tracing | LangGraph + LangSmith |
| State + queue | Supabase Postgres + `pgmq` extension |
| Compute | Railway (two services from one image) |
| Infrastructure as code | Terraform (Railway + Supabase providers) |

---

## 1. Architecture

### 1.1 Request flow

```
                  ┌─────────────┐
   HTTP request → │   API svc   │  FastAPI on Railway
                  │  validate   │
                  │  + enqueue  │
                  └──────┬──────┘
                         │ pgmq.send()
                         ▼
              ┌──────────────────────┐
              │  Supabase Postgres   │
              │  - pgmq queue        │
              │  - loads             │
              │  - events            │
              │  - tool_calls        │
              │  - timers            │
              │  - tasks / issues    │
              └──────────┬───────────┘
                         │ pgmq.read()  (long-poll loop)
                         ▼
                  ┌─────────────┐
                  │  Worker svc │  LangGraph agent on Railway
                  │  agent run  │
                  └─────────────┘
```

### 1.2 Component responsibilities

**API service.** Does as little as possible. Validate the payload against the input schema, persist the event row, `pgmq.send()` a message, return `202 Accepted`. No agent logic.

**Worker service.** Consumes the queue: `pgmq.read(queue, vt, qty)` → process → `pgmq.delete(msg_id)` on success, or `pgmq.archive(msg_id)` on permanent failure. The visibility timeout (`vt`) makes a crashed worker's message reappear automatically for retry.

**Supabase Postgres.** Single source of truth — both the queue (`pgmq`) and all persistent state live here. One connection string, transactional enqueue, no extra infra.

### 1.3 Load isolation & concurrency safety

Two events for the same load must not run concurrently and corrupt state.

- When the worker picks up a message, it takes a **`pg_advisory_xact_lock`** keyed on a hash of `load_id`.
- Events for **different loads run fully in parallel**; events for the **same load serialize**.
- Read load state → run agent → write new state + tool-call records, all in **one transaction**.
- If the lock cannot be acquired, let the message's visibility timeout expire so it retries later.

### 1.4 Timers / scheduled follow-ups

The challenge is explicit: timers are **not** a `task_instruction_type`.

**Chosen approach:** a `timers` table with `fire_at_utc` + a poller loop that finds due timers and `pgmq.send()`s them back as a `timer_fired` event.

- Rejected alternative: pgmq delayed messages — simpler, but cancellation/visibility is harder, and `cancel_timer` / `cancel_timers` must work.
- The table approach makes cancellation a simple row update and keeps timers fully inspectable.
- The poller runs as a loop inside the worker process for the one-week timebox (a separate Railway service is the cleaner-but-heavier alternative).

### 1.5 The agent (LangGraph)

Each event is one graph run. Proposed node sequence:

```
classify_sender → select_sop_branch → gather_context → decide_actions → execute_tools → persist_state
```

- `classify_sender` — broker senders short-circuit to a recorded no-op.
- `select_sop_branch` — pick the ETA or Confirm-Delivery branch.
- `gather_context` — read-only tool calls (`check_attachment`, `get_load_info`).
- `decide_actions` — choose tools to call.
- `execute_tools` — call mocked tools, record each call.
- `persist_state` — write final state change.

LangGraph's **Postgres checkpointer** doubles as per-load session memory for follow-up events.

### 1.6 Observability

- **LangSmith** traces cover the agent portion (free with LangChain).
- **Structured logs** also emitted with `load_id`, `event_id`, event type, selected SOP branch, tool calls, and final state change — needed because the rubric wants logs connecting API → queue → worker, which LangSmith alone does not cover.

### 1.7 Model fallback

LangChain `.with_fallbacks([...])` on the chat model: primary model → fallback model → deterministic **mock model** for evals. Selectable via environment variable so evals can force the mock.

### 1.8 Customer-specific behavior

The highest-value design decision. Behavior stays **declarative**:

- One config file per customer (`customers/customer_*.yaml`) describing escalation channel, geofence radius, timer minutes, POD policy, lumper handling, and visibility rules.
- SOP files become prompt templates with slots; customer config fills the slots and drives deterministic branches (geofence math, timer creation).
- **No `if customer == "b"` logic scattered through the code** — one config object, read in one place.

---

## 2. Repository Structure

```
freighthero-watchtower/
├── README.md
├── AI_USAGE.md
├── docker-compose.yml          # local: api + worker + supabase/local pg+pgmq
├── Dockerfile                  # one image, two start commands
├── pyproject.toml
├── .env.example
│
├── app/
│   ├── api/
│   │   ├── main.py             # FastAPI app
│   │   ├── routes.py           # the 5 endpoints
│   │   └── schemas.py          # Pydantic models from challenge-input.schema.json
│   │
│   ├── worker/
│   │   ├── main.py             # pgmq consume loop
│   │   ├── lock.py             # advisory lock per load_id
│   │   └── scheduler.py        # timer poller
│   │
│   ├── agent/
│   │   ├── graph.py            # LangGraph definition
│   │   ├── nodes/              # classify, select_branch, decide, execute
│   │   ├── prompts/            # SOP-derived prompt templates
│   │   └── models.py           # LLM + fallback chain config
│   │
│   ├── sops/
│   │   ├── eta_checkpoint.md
│   │   └── confirm_delivery.md
│   │
│   ├── customers/
│   │   ├── base.py             # CustomerProfile schema
│   │   ├── customer_a.yaml
│   │   ├── customer_b.yaml
│   │   └── customer_c.yaml
│   │
│   ├── tools/
│   │   ├── registry.py         # tool definitions + dispatch
│   │   ├── communication.py    # send_sms, send_email, forward_email, send_slack_message
│   │   ├── state.py            # update_load_state, update_eta
│   │   ├── timers.py           # create_timer, cancel_timer, cancel_timers
│   │   ├── human_work.py       # create_task, create_issue
│   │   └── recorder.py         # durable tool_call records
│   │
│   ├── db/
│   │   ├── client.py           # supabase / pg connection
│   │   ├── queue.py            # pgmq send/read/delete/archive wrappers
│   │   ├── repositories.py     # loads, events, tool_calls, timers
│   │   └── migrations/         # SQL: tables + pgmq enable
│   │
│   └── observability/
│       └── logging.py          # structured logger
│
├── evals/
│   ├── run_evals.py            # single-command harness
│   ├── assertions.py           # required/forbidden tool-call checks
│   ├── fixtures/test-cases.json
│   └── EVAL_REPORT.md
│
├── infra/
│   ├── main.tf                 # Railway services + Supabase project
│   ├── railway.tf
│   ├── supabase.tf
│   ├── variables.tf
│   └── outputs.tf
│
└── docs/
    └── ARCHITECTURE.md          # the write-up
```

---

## 3. Build Phases

### Phase 1 — Foundations
- Repo scaffold, `pyproject.toml`, `Dockerfile`, `docker-compose.yml`.
- DB migrations: `loads`, `events`, `tool_calls`, `timers`, `tasks`, `issues`; enable `pgmq`.
- `db/client.py` and `db/queue.py` (pgmq wrappers).

### Phase 2 — API service
- Pydantic models from `challenge-input.schema.json`.
- The 5 endpoints (`/loads`, `/submit-task`, `/events/*`).
- Validate → persist event → `pgmq.send()` → `202`.

### Phase 3 — Worker skeleton
- pgmq consume loop with advisory lock per `load_id`.
- Single-transaction read-state / write-state cycle.
- Structured logging wired through.

### Phase 4 — Tools
- Tool registry + all mocked tools.
- Durable tool-call records (`load_id`, `event_id`, timestamp).

### Phase 5 — Agent
- LangGraph graph + nodes.
- SOP prompt templates + customer config loading.
- Model fallback chain (incl. mock model).

### Phase 6 — Customer behavior
- `customer_a/b/c.yaml` profiles.
- Wire profiles into prompts + deterministic branches (geofence, timers).

### Phase 7 — Timers
- `timers` table + poller loop.
- `create_timer` / `cancel_timer` / `cancel_timers`.

### Phase 8 — Evals
- `run_evals.py` single-command harness.
- Required + forbidden tool-call assertions; state-transition checks.
- `EVAL_REPORT.md` with pass/fail, gaps, hidden-risk areas.

### Phase 9 — Deployment
- Terraform: Railway services + Supabase project.
- pgmq enablement stays in SQL migrations (not TF).
- Capture deployed-run logs/traces as evidence.

### Phase 10 — Docs
- `ARCHITECTURE.md` write-up: tradeoffs, customer-mapping approach, what was omitted.
- `AI_USAGE.md`.

---

## 4. Known Gaps & Decisions to Revisit

- **Railway Terraform provider** is community-maintained; it provisions services, env vars, and deployments, but the GitHub-repo-deploy trigger may need to be set up via Railway's GitHub integration manually. Document this.
- **Supabase Terraform provider** manages the project, but `pgmq` enablement is a SQL migration — it lives in `db/migrations/`, not Terraform. Document this.
- **Timer scheduler placement** — in-process loop inside the worker for the timebox; a third Railway service is the cleaner separation if time allows.