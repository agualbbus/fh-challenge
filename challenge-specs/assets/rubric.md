# Evaluation Expectations

Use this as a guide for what we will look for when reviewing submissions. We care about the quality of the candidate's engineering judgment across the whole solution.

## Production Architecture

- Clear API/worker separation with durable async execution.
- Persistent per-load state
- Load isolation and concurrency safety.
- Sensible data model for loads, events, customer-specific rules, tool calls, timers, tasks, and issues.
- Model fallback strategy is configurable and observable.
- Simplicity and maintainability; no unnecessary framework sprawl.

## SOP and Agent Behavior

- Correctly implements ETA checkpoint branches.
- Correctly implements confirm delivery/POD branches.
- Customer A/B/C differences change behavior without hardcoded one-off logic.
- Correct tool use and forbidden-tool avoidance.
- Channel matching and concise communication.
- Text and attachment handling through `check_attachment`.
- Handles no-action and broker-ignore cases.
- Clear handling of ambiguous inputs.

## Evals and Testing

- Visible fixture cases pass with clear assertions.
- Candidate explains meaningful edge cases and residual risks.
- Tests assert both required and forbidden tool calls.
- Tests cover customer-specific variations.
- Eval command is simple and reproducible.
- Eval report honestly discusses gaps and hidden-risk areas.

## Deployment and Security

- Application is deployed to a real cloud endpoint.
- Dockerized services run locally and in cloud.
- IaC provisions the meaningful resources.
- Secrets are not committed and are handled sensibly.
- Basic least-privilege/security posture is documented.
- Deployment notes are clear enough for review.

## Observability and Debuggability

- Logs or traces connect API request, queue event, worker processing, and tool calls.
- Traces/logs show selected SOP branch and rationale.
- Deployed run evidence is provided.
- Error paths are visible and actionable.
- Cost/latency or model-provider metadata is captured or discussed.

## Product and Engineering Judgment

- Clear tradeoffs between speed, correctness, and scope.
- Candidate avoids overbuilding and explains what was intentionally omitted.
- Customer-specific behavior design would scale beyond three customers.
- Written communication is clear and operationally useful.
- AI-assistant usage is disclosed with ownership of final decisions.

## Strong Signals

- Treats evals as infrastructure, not a demo afterthought.
- Uses tool-call and state assertions to make behavior reviewable.
- Keeps customer-specific behavior declarative.
- Makes hidden state inspectable through logs/traces.
- Degrades safely when the model or a tool fails.