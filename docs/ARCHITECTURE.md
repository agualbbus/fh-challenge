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
| CI/CD (AWS) | GitHub Actions OIDC → ECR → ECS force deploy on `main` |

## Request flow

1. Client `POST /loads` or event endpoint → API returns `202` after SQS publish.
2. Worker receives message → `graph.ainvoke(..., thread_id=load-{load_id})`.
3. Graph invokes `create_agent` (or pre-agent guards) → merges `tool_calls[]` and `load_state` into checkpoint.
4. Evals read state via `graph.aget_state` (no read HTTP API).

## Design decisions

- **Agent:** LangChain `create_agent` with SOP system prompt over OpenRouter. The agent's final answer is a JSON object (`summary`, `sop`, `rationale`) parsed by `PydanticOutputParser`.
- **Durable execution:** LangGraph `@task` wraps agent decisions; `durability="sync"` on invoke.
- **Eval source of truth:** Checkpointed `tool_calls` + `milestone` in Postgres.
- **Timers:** `create_timer` schedules delayed SQS message (`kind=timer`); max 900s delay on SQS (EventBridge for longer in AWS).
- **Broker ignore:** Pre-agent guard in orchestrator; event still accepted and logged.

## Load data lifecycle

`load_data` (stops, contacts, references, appointment) is sourced **only** from the `POST /loads` seed request body. There is no external TMS or database lookup at runtime.

1. API validates `LoadSeedRequest` and publishes a `seed` `WorkMessage` carrying `{load_data, milestone}` to SQS (`app/api/routes.py:_seed_from_load`).
2. `seed_node` calls `init_load_state(load_id, payload)` (`app/worker/merge.py`), writing `load_data` into `LoadGraphState.load_state.load_data` in the Postgres checkpoint.
3. Subsequent reads — tools, `app/worker/load_data.py` helpers, the SOP prompt's `<load_state>` block — resolve fields from that in-checkpoint dict.
4. Updates flow through `merge_load_data` (one level deep into `load_data`) applied to agent `state_delta`s; nothing else mutates it.

The seed payload is therefore the single source of truth for the load record; the checkpoint is its durable home.

## Deterministic tracking branch

Tracking pings (`event_type=tracking`) bypass the LLM entirely. `event_node` calls `app/worker/tracking.handle_tracking_ping`, which maintains a `session["consecutive_geofence_pings"]` counter. When three consecutive fresh pings fall within the customer's `geofence_radius_miles`, it synthesizes `update_load_state(at_delivery)` and `cancel_timers` `ToolCallRecord`s, merges them into the checkpoint, and clears `active_timers` — no LLM call needed.

## Attachment-driven SOP transition

A POD or other attachment arriving while the load is still on the ETA checkpoint SOP implies the driver has implicitly arrived. `event_node` detects `attachments` in the inbound_communication payload and promotes `active_task` from `delivery_eta_checkpoint` to `confirm_delivery` via `merge_load_data` before the agent is invoked. This gives the agent access to `check_attachment`, `forward_email`, and the confirm-delivery tool surface without requiring an explicit `/submit-task` call from the caller.

## Intentional gaps

- Timer-fired agent branches return noop; ETA follow-up `create_timer` is recorded in the checkpoint but the timer re-entry agent decision is not yet implemented.
- Live deploy evidence and full fixture pass against the public endpoint still pending.
- **No end-to-end distributed tracing.** LangSmith traces only the worker leg (graph + agent + tool calls). The API → SQS hop is not instrumented, so an inbound HTTP request and its eventual worker run are not stitched into a single trace. Production would propagate a trace/correlation ID from the API into SQS message attributes and pick it up in the consumer (OpenTelemetry across FastAPI + boto3 + the LangGraph run), giving one span tree per `load_id` event across both processes.
- **Customer config as a service.** Customer-specific behavior currently lives in committed YAML (`app/customers/*.yaml`) loaded at process start via `app/customers/base.py:_load_profiles`. This is the right shape for the challenge — declarative, diffable, reviewable — but in production a Customer Service (HTTP/RPC, backed by a database with per-tenant audit and versioning) should front this: profiles loaded on demand, cached with a TTL, hot-reloadable without redeploy, and able to drive per-customer message templates (e.g., `first_arrival_message`) and feature flags. Replacing the YAML loader with a client against that service is a single seam.

See [research/implementation-spec.md](research/implementation-spec.md) for full detail.
