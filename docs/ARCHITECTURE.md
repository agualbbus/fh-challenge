# Architecture

FreightHero Watchtower is a thin HTTP API over **SQS FIFO** and **LangGraph** with **PostgreSQL** checkpoints. Each load uses `thread_id = load-{load_id}` for durable per-load state.

## Components

| Layer | Responsibility |
| --- | --- |
| FastAPI (`app/api/`) | Validate ingress, `202 Accepted`, publish work items to SQS |
| SQS FIFO | Decouple API from agent; `MessageGroupId = load_id` for ordering |
| Worker (`app/worker/`) | Long-poll SQS, LangGraph graph, `create_agent`, router |
| PostgreSQL | `AsyncPostgresSaver` checkpoint store |
| Customer YAML | Declarative A/B/C behavior via `CustomerProfile` |
| LangSmith (optional) | Traces when `LANGCHAIN_TRACING_V2=true` |

## Request flow

1. Client `POST /loads` or event endpoint → API returns `202` after SQS publish.
2. Worker receives message → `graph.ainvoke(..., thread_id=load-{load_id})`.
3. Graph invokes `create_agent` (or pre-agent guards) → merges `tool_calls[]` and `load_state` into checkpoint.
4. Evals read state via `graph.aget_state` (no read HTTP API).

## Design decisions

- **Agent:** LangChain `create_agent` with SOP system prompt; `MODEL_MODE=mock` uses fixture mock LLM (no OpenRouter in CI).
- **Durable execution:** LangGraph `@task` wraps agent decisions; `durability="sync"` on invoke.
- **Eval source of truth:** Checkpointed `tool_calls` + `milestone` in Postgres.
- **Timers:** `create_timer` schedules delayed SQS message (`kind=timer`); max 900s delay on SQS (EventBridge for longer in AWS).
- **Broker ignore:** Pre-agent guard in orchestrator; event still accepted and logged.

## Intentional gaps

- Confirm-delivery branches beyond first slice (Phase 4+).
- Timer-fired agent branches return noop until ETA follow-up cases are implemented.
- ECS task definitions deferred until local evals pass.
- **Customer config as a service.** Customer-specific behavior currently lives in committed YAML (`app/customers/*.yaml`) loaded at process start via `app/customers/base.py:_load_profiles`. This is the right shape for the challenge — declarative, diffable, reviewable — but in production a Customer Service (HTTP/RPC, backed by a database with per-tenant audit and versioning) should front this: profiles loaded on demand, cached with a TTL, hot-reloadable without redeploy, and able to drive per-customer message templates (e.g., `first_arrival_message`) and feature flags. Replacing the YAML loader with a client against that service is a single seam.

See [research/implementation-spec.md](research/implementation-spec.md) for full detail.
