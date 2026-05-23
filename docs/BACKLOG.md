# FreightHero Watchtower — Implementation Backlog

Kickoff backlog derived from [dos/research/implementation-spec.md](../dos/research/implementation-spec.md).

## Phase 1 — Repos and IaC (start here)

- [x] Initialize `freighthero-watchtower` app repo structure (`app/`, `evals/`, `infra/`, `docs/`)
- [x] Python via **uv**: `uv python pin 3.12`, `uv init`, `uv add fastapi uvicorn temporalio pydantic langfuse pytest pytest-asyncio`, commit `uv.lock`
- [x] Add Makefile targets: `install`, `dev-api`, `dev-worker`, `test`, `eval` (all via `uv run`)
- [x] Add `Dockerfile` (uv-based install from `uv.lock`) and `docker-compose.yml` (api, worker; Temporal dev for persistence)
- [x] Add `.env.example` for Temporal, DB, model keys, and Langfuse (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`, `LANGFUSE_ENABLED`)
- [x] Implement `GET /health` on FastAPI stub
- [x] Implement `app/worker.py` registering stub `LoadWorkflow`
- [ ] Sign up Temporal Cloud; create namespace with API key auth (`terraform apply` — manual, see `infra/README.md`)
- [x] Add `infra/temporal.tf` + `infra/aws_ecs.tf` skeleton (ECR, ECS cluster, two services, ALB, Secrets)
- [x] Document local run in root `README.md`

## Phase 2 — Agent harness

- [ ] Copy SOPs from `challenge-specs/assets/sops/` to `app/sops/`
- [ ] Pydantic schemas from `challenge-input.schema.json`
- [ ] Tool registry + recorder (all tools from `challenge-specs/assets/tools.md`)
- [ ] Customer YAML: `customer_a`, `customer_b`, `customer_c`
- [ ] `evals/run_evals.py` + `evals/assertions.py`
- [ ] `docs/ARCHITECTURE.md`, `docs/DEPLOYMENT.md`
- [ ] `.cursor/rules/` for determinism, customer config, broker ignore, eval discipline
- [ ] Model fallback chain (`MODEL_MODE=mock` for CI)
- [ ] Langfuse: `app/observability/langfuse.py`, OTel exporter, `@observe` on `run_agent_activity` ([Temporal + Langfuse](https://langfuse.com/integrations/frameworks/temporal))
- [ ] Verify one trace in Langfuse UI after `3b` manual run; save trace URL to `docs/evidence/`

## Phase 3 — First feature

- [ ] `POST /loads` → start workflow with seed
- [ ] `POST /events/inbound-communication` → signal-with-start
- [ ] Activity: load-info question branch (address found)
- [ ] Eval: pass `3b_load_question_found`
- [ ] Activity: missing info + Customer B escalation
- [ ] Eval: pass `3c_load_question_missing`

## Phase 4+ — Visible fixtures (priority order)

- [ ] `3k_broker_email_ignore`
- [ ] `3d_truck_broken`
- [ ] `3f_driver_provides_eta` (+ time-skipping timer test)
- [ ] `3h_fresh_tracking_three_pings_in_geofence`
- [ ] `3i_not_tracking_driver_says_arrived`
- [ ] `3j_not_tracking_driver_sends_pod`
- [ ] Confirm delivery + lumper branches (Customer C `forward_email`)

## Submission

- [ ] Deploy to AWS; capture public API URL
- [ ] Run evals against deployed endpoint; save log/trace evidence (include Langfuse trace link)
- [ ] Write `AI_USAGE.md` and finalize `evals/EVAL_REPORT.md`
