# AI Engineer Technical Challenge

## Context

FreightHero builds AI operators for freight brokerage workflows. The production AI Watchtower system receives load events, tracking pings, inbound driver/broker communications, and scheduled follow-ups. It then uses SOP-driven agents to decide whether to reply, update state, create a task for a human operator, create an issue, schedule a follow-up, or ignore the event.

This take-home asks you to build a small production-like version of that system for two workflows:

1. **On Route to Delivery / ETA Checkpoint**: monitor delivery ETA, tracking, arrival, driver questions, and operational exceptions while a driver is en route.
2. **Confirm Delivery**: after arrival, confirm unloading, collect/validate POD, handle lumper receipts, and manage follow-ups.

We are looking for judgment: a working slice that shows how you design, build, test, deploy, observe, and explain an agentic application in a realistic operational setting.

## Timebox

Target: **one week**.

Use your judgment on depth. A strong submission should be production-shaped, not feature-complete. Prefer a small system with clear boundaries, useful tests, and real deployment over a broad demo that cannot be operated or evaluated.

Completeness matters, but we do not expect every possible branch or production concern to be fully finished in one week. Include documentation for anything meaningful you did not complete: gaps, next steps, tradeoffs, and what you would do differently with more time.

## Stack Policy

Python is required for the application implementation. You may choose the web framework, queue, database, agent framework, and cloud provider.

Required architectural properties:

- API and agent execution are decoupled by a queue or durable async work mechanism.
- Per-load state is persisted outside process memory.
- Events for the same load are isolated from other loads and handled safely under concurrency.
- Agent behavior is driven by SOP content and customer-specific workflow differences.
- Tools are mocked, but the tool calls must be recorded and testable.
- The system is containerized.
- The deployed version runs in a real cloud account using infrastructure as code.

## Required Public API

Expose the following write endpoints. You do **not** need to expose read APIs for load or event state.

Required endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/loads` | Create or seed a load with customer ID and initial load data. |
| `POST` | `/submit-task` | Submit a workflow task for an existing load, such as `delivery_eta_checkpoint` or `confirm_delivery`. |
| `POST` | `/events/inbound-communication` | Enqueue an inbound SMS/email-style message. |
| `POST` | `/events/tracking` | Enqueue a tracking ping. |
| `POST` | `/events/load-update` | Enqueue an update to load data or milestone state. |

Scheduled follow-ups should be modeled separately from `/submit-task`. They can re-enter processing as time-based events, timer callbacks, delayed queue messages, or an equivalent scheduler input, but they should not be represented as a task instruction type.

## Required Behavior

Your implementation must process the visible cases in `assets/fixtures/test-cases.json` and should be easy for us to run against hidden variants.

At minimum, your agent must support:

- SOP branch selection for ETA checkpoint and confirm delivery.
- Customer-specific behavior for Customer A, B, and C.
- Channel matching for driver-facing replies.
- Broker messages are ignored. Do not reply to brokers or process broker messages as action triggers in this challenge.
- Mocked tool use for SMS, email, email forwarding, Slack, attachment checks, timers, state updates, tasks, issues, and ETA updates.
- Text and attachment metadata inputs. You do not need real OCR; use the provided attachment metadata and `check_attachment` mock result.
- Model fallback strategy. This may be a real provider fallback, a configurable mock fallback, or both.
- Short-term per-load session state so follow-up events can use prior context.

## SOP Usage and Organization

The SOP files in `assets/sops/` are guideline assets, not a required runtime format. They describe shared workflow behavior. `assets/customer-expectations.md` describes customer-specific differences. Your solution should decide how those two sources become agent instructions and runtime behavior.

You may use the SOPs as-is, modify the content, split them into smaller files, create customer-specific fragments, compose prompt sections dynamically, or organize the SOP material in another way. We are interested in your approach to managing SOPs when many brokers/customers have related workflows with small but important differences. In your write-up, explain how you map customer expectations into the agent behavior, the tradeoffs of your chosen approach, and what you would do differently as the number of custom workflows grows.

## Deployment Requirements

Deploy the application to a real cloud account you control.

Required deliverables:

- Dockerfile(s) and local run instructions.
- Infrastructure as code.
- Public API endpoint for the deployed service.
- Description of cloud resources used.
- Notes on secrets management and least-privilege assumptions.
- Logs or trace evidence from at least one deployed test run.

## Observability Requirements

Acceptable trace surfaces include one or more of:

- structured logs with `load_id`, `event_id` or request ID, event type, selected SOP branch, tool calls, and final state change;
- public LangSmith, OpenTelemetry, Honeycomb, Datadog, or equivalent trace links;
- cloud log links or screenshots;
- an exported trace artifact checked into your submission, such as JSONL logs from a run.

We should be able to answer: "Why did the agent call these tools for this event?"

## Evaluation Requirements

Include an eval/test harness that can be run locally.

Required:

- assertions over tool calls and state transitions for the visible cases;
- a single command that runs the eval suite;
- a short eval report covering pass/fail results, remaining gaps, and which hidden cases you expect to be risky.

## Provided Assets

- `assets/background.md`: freight and Watchtower concepts.
- `assets/sops/on_route_to_delivery_eta_checkpoint.md`: ETA checkpoint SOP.
- `assets/sops/confirm_delivery.md`: confirm delivery SOP.
- `assets/tools.md`: mocked tool contracts.
- `assets/schemas/challenge-input.schema.json`: reference JSON Schema for the payloads accepted by `/loads`, `/submit-task`, and `/events/*`. You may use it directly for request validation, translate it into Python/Pydantic models, or implement an equivalent contract. It is an API input contract, not agent logic or customer configuration.
- `assets/customer-expectations.md`: Customer A/B/C behavior expectations.
- `assets/fixtures/test-cases.json`: visible cases and expected outcomes.
- `assets/rubric.md`: scoring guide.

These assets are examples to guide your implementation. You do not need to use them exactly as written, but we recommend staying close to them because they are simplified versions of patterns from our real application.

## AI Assistant Policy

You may use LLM coding assistants. We expect that you will.

Include a short `AI_USAGE.md` in your submission:

- tools/models used;
- which parts were generated or heavily assisted;
- which decisions you made manually;
- examples where you rejected or corrected AI-generated output.

We evaluate engineering judgment, verification discipline, and ownership of the final result, not whether you typed every line by hand. Remember, all produced code is your responsibility and you must be able to explain it.

## Submission

Send us:

1. GitHub repository URL.
2. Deployed public API base URL.
3. How to run locally.
4. How to run evals.
5. Trace/log evidence from a deployed run.
6. Short architecture and tradeoff write-up.
7. `AI_USAGE.md`.

If you have any questions, don't hesitate to send us an email at tech@freighthero.ai.

Email title: "AI Engineer position - your name"
