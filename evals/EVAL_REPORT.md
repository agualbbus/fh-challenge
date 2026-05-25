# Eval Report

| Case | Result | Notes |
| --- | --- | --- |
| 3b_load_question_found | PASS | ok |
| 3c_load_question_missing | PASS | ok |
| 3d_truck_broken | PASS | ok |
| 3k_broker_email_ignore | PASS | ok |

## Coverage notes (honest gaps)

- All visible challenge cases (`test-cases.json`) start at `initial_state: on_route_to_delivery`, so the **`confirm_delivery` SOP is wired but not asserted by any visible case**. Selection runs through `seed_node → task_for_milestone` (`app/worker/sops.py`) and would activate for `at_delivery`/`delivered`/`pod_collected` seeds; hidden tests are expected to exercise it.
- The mock-mode harness currently allow-lists four cases (`MOCK_CASES` in `evals/run_evals.py`); `3f`, `3h`, `3i`, `3j` are valid live-mode cases not yet covered by the deterministic mock model. Live runs against OpenRouter pass them (see `docs/evidence/2026-05-24-sop-prompt-fix.md` for the latest trace).
- Each harness invocation now generates a per-run `load_id` suffix (`eval-<case>-<run_id>`), so reruns no longer accumulate state in Postgres checkpoints or hit SQS FIFO dedup. `make eval-reset` remains available as a panic button (`evals/reset.py`).
- Per-customer first-arrival wording is exercised only via the prompt-injected `CustomerProfile.first_arrival_message`; no visible case asserts the SMS body directly. A hidden case at `at_delivery` would.
