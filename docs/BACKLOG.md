# FreightHero Watchtower — Implementation Backlog

Kickoff backlog derived from [implementation-spec.md](research/implementation-spec.md).

## Phase 1 — Repos and IaC

- [x] Initialize repo structure (`app/`, `evals/`, `infra/`, `docs/`)
- [x] Python via **uv**, `uv.lock`, Makefile targets
- [x] Dockerfile + `docker-compose.yml` + `.dockerignore`
- [x] `GET /health`, LangGraph + SQS worker
- [x] Terraform AWS skeleton (RDS Postgres, SQS FIFO, ECS/ALB)
- [x] README local-run section

## Phase 2 — Agent harness

- [x] Copy SOPs to `app/sops/`
- [x] Pydantic schemas from `challenge-input.schema.json`
- [x] Tool registry + recorder (all tools from `tools.md`)
- [x] Customer YAML: `customer_a`, `customer_b`, `customer_c`
- [x] `evals/run_evals.py` + `evals/assertions.py`
- [x] `docs/ARCHITECTURE.md`, `docs/DEPLOYMENT.md`
- [x] `.cursor/rules/watchtower.mdc`
- [x] ChatOpenRouter chat model in `app/worker/llm.py`
- [x] Load all sections of the active task's SOP into the system prompt (replace single-section slice in `build_system_prompt`), letting the agent pick the branch instead of hard-coding `load_information_question`
- [ ] Verify one trace in LangSmith UI; save URL to `docs/evidence/` (set env vars directly)

## Phase 3 — First feature

- [x] `POST /loads` → SQS seed message
- [x] `POST /events/inbound-communication` → SQS event message
- [x] Graph: load-info question branch (address found)
- [x] Eval: `3b_load_question_found`
- [x] Graph: missing info + Customer B escalation
- [x] Eval: `3c_load_question_missing`
- [ ] Re-run HTTP evals against full docker compose stack

## Phase 4+ — Visible fixtures (priority order)

- [ ] `3k_broker_email_ignore`
- [ ] `3d_truck_broken`
- [ ] `3f_driver_provides_eta` (+ timer via SQS delay injection in tests)
- [ ] `3h_fresh_tracking_three_pings_in_geofence`
- [ ] `3i_not_tracking_driver_says_arrived`
- [ ] `3j_not_tracking_driver_sends_pod`
- [x] Confirm delivery selectable by milestone (`seed_node` → `task_for_milestone`)
- [x] Customer C lumper config: `forward_email` + `review_task_fallback` + `enforce_pod_handling`
- [x] Per-customer `first_arrival_message` templates in YAML
- [ ] Confirm-delivery fixtures (visible cases all start `on_route_to_delivery`; SOP wired but unexercised by visible tests)

## Submission

- [ ] Deploy to AWS; capture public API URL
- [ ] Run evals against deployed endpoint; save log/trace evidence
- [ ] Write `AI_USAGE.md` and finalize `evals/EVAL_REPORT.md`
