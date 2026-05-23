# Temporal for FreightHero Watchtower: Architecture & Deployment Decision Brief

## TL;DR
- **Yes, use Temporal Cloud, not self-hosted Temporal on AWS.** Temporal Cloud hosts only the orchestration service; your Python Worker process always runs in your own infrastructure. For a one-week take-home, Temporal Cloud is self-serve, has a $1,000 free-credit trial, and avoids the Cassandra/PostgreSQL/Elasticsearch operational burden that the docs explicitly warn small teams about.
- **AWS is appropriate, but only for the Worker + a thin FastAPI process** — deploy both as containers on ECS Fargate (or Fly.io if you'd rather skip VPC plumbing). Do not self-host the Temporal Server. The lowest-overhead path is: Temporal Cloud (managed control plane) + one ECS Fargate service that runs your FastAPI HTTP shim and your Temporal Worker, wired with Terraform.
- **Yes, you still need a thin HTTP layer in front of Temporal.** The Temporal SDK Client is a gRPC library, not a public REST API. Keep FastAPI as a small shim that translates `POST /loads`, `POST /events/*`, `POST /submit-task` into `client.start_workflow(...)` and `handle.signal(...)` calls — using `load_id` as the Workflow ID.

---

## Key Findings

### 1. Temporal Cloud is a managed control plane only — Workers always run in your infra
The Temporal Cloud overview is unambiguous: "Temporal Cloud never executes your application code. Workers run in your environment, connecting to Temporal Cloud over encrypted channels." The Workers concept page reinforces it: "the Temporal Service (including the Temporal Cloud) doesn't execute any of your code (Workflow and Activity Definitions) on Temporal Service machines. The Temporal Service is solely responsible for orchestrating State Transitions and providing Tasks to the next available Worker Entity."

What Temporal Cloud gives you for free (operationally):
- The Temporal Server (Frontend, History, Matching, internal Worker services).
- The persistence layer (no Cassandra/Postgres/Elasticsearch to manage).
- 3-AZ synchronous replication. Per `docs.temporal.io/cloud/sla`: "Standard Temporal Cloud deployment provides 99.99% availability and a contractual service level agreement (SLA) of 99.9% guarantee against service errors."
- A hosted Web UI at `cloud.temporal.io` and a per-namespace gRPC endpoint at `<namespace>.<account>.tmprl.cloud:7233`.

What you still own:
- Your Worker process(es) (the Python container that hosts Workflow + Activity code).
- Your HTTP API process (FastAPI) that uses the Temporal Client SDK to start workflows / send Signals.
- Secrets management for the API key or mTLS cert.

### 2. Signup, auth, pricing for a take-home
- **Self-service signup** is available at `cloud.temporal.io`; no sales call required. Per the official pricing docs: "The Essentials tier is priced at the greater of $100/month or 5% of your Temporal Cloud consumption. The Business tier is priced at the greater of $500/month or 10% of Temporal Cloud consumption." New accounts get **$1,000 in free credits**, and the AWS Marketplace listing adds a 3-month free trial on top of that. For a one-week project with very low traffic (a few thousand actions tops), you will not exhaust the trial credit.
- **Authentication**: choose **API keys** when creating the namespace ("Allow API key authentication"). API keys are bearer tokens — simpler than mTLS, and the *only* auth method the Terraform Cloud provider and Cloud Ops API support for automation. mTLS is also supported if you already have a CA, but generating and rotating client certs is unnecessary friction for a one-week build.
- **Connection from Python**: set `TEMPORAL_ADDRESS=<ns>.<acct>.tmprl.cloud:7233`, `TEMPORAL_NAMESPACE=<ns>.<acct>`, `TEMPORAL_API_KEY=...`, then `Client.connect(...)` from `temporalio`.

### 3. Self-hosting Temporal is the wrong choice for this challenge
A production self-hosted deployment requires:
- 3+ Temporal Server pods/tasks (Frontend, History, Matching, internal Worker — typically packaged together but still four internal services).
- A persistence store: PostgreSQL/MySQL is supported, but the Temporal docs and community engineering reports warn that Postgres "is not ideal for medium-to-large-scale systems"; serious deployments use Cassandra.
- A visibility store: Elasticsearch is "recommended for any Temporal Service setup that handles more than a few Workflow Executions" — Cassandra can't even be used as the visibility store.
- Schema migrations via `temporal-sql-tool` / `temporal-cassandra-tool` / `temporal-elasticsearch-tool` on every server upgrade.

Concrete cost numbers from Automation Atlas's April 2026 "Temporal Self-Hosted Pricing" analysis: 3× m6i.xlarge Temporal Server nodes ≈ $330/month + RDS PostgreSQL db.m6g.large (200 GB) ≈ $180/month + 3-node OpenSearch (t3.medium.search) ≈ $180/month ≈ $690/month total; "Without Elasticsearch (standard visibility only), the total falls to approximately $480–$610/month." That's *before* any SRE labor. Temporal's official Attentive case study quantifies the labor side: "By migrating off their self-hosted Temporal server to Temporal Cloud, the team was able to capture an estimated $30,000/month in cost savings" — plus "eight engineering-months last year on Temporal maintenance alone."

For a one-week solo take-home, you will spend more time on Helm/ECS plumbing for the server than on the actual freight logic. Don't do it.

### 4. The Temporal Python SDK is GA and idiomatic
The Python SDK went GA on **March 6, 2023** ([Temporal blog, "Python SDK: The release"](https://temporal.io/blog/python-sdk-the-release): "Announcing the GA release of our Python SDK, allowing Python devs to write durable code"; the companion engineering post adds "Python is now a fully-supported workflow language in Temporal, and our use of native asyncio constructs makes it a perfect fit for Python developers looking to write durable workflows"). It uses native `async`/`await`, decorators (`@workflow.defn`, `@workflow.run`, `@activity.defn`, `@workflow.signal`, `@workflow.query`, `@workflow.update`), and a custom durable asyncio event loop. `asyncio.sleep()` inside a workflow is a durable timer; activities can be async, threaded, or multiprocess.

### 5. Workers, Task Queues, Workflows, Activities — the runtime model
A Worker is a long-running process inside your container that:
1. Opens a gRPC long-poll connection to Temporal Cloud.
2. Polls a named Task Queue (e.g., `freight-watchtower`).
3. For each Workflow Task: runs your `@workflow.defn` code, which deterministically issues Commands (start activity, sleep, complete).
4. For each Activity Task: runs your `@activity.defn` function with at-least-once semantics, retries, and heartbeats.

Workers don't take inbound HTTP traffic. The official ECS deployment guide is explicit: "There's no `load_balancer` block. The Worker doesn't accept inbound connections, which dramatically simplifies the infrastructure compared to a typical ECS service... Egress-only security group. Zero ingress rules."

### 6. Per-load isolation comes for free via Workflow ID
The Workflow ID docs state: "Temporal guarantees that only one Workflow Execution with a given Workflow Id can be in an Open state at any given time" and "It is not possible for a new Workflow Execution to spawn with the same Workflow Id as another Open Workflow Execution, regardless of the Workflow Id Reuse Policy."

Combined with the message-handling guarantee from `docs.temporal.io/handling-messages` — "Every time the Workflow wakes up--generally, it wakes up when it needs to--it will process messages in the order they were received, followed by making progress in the Workflow's main method. This execution is on a single thread" — this means: **set `workflow_id = f"load-{load_id}"` and Temporal automatically gives you per-load serialization and isolation.**

### 7. Signals, Signal-with-Start, Queries, Updates, Timers
- **Signals**: asynchronous messages from outside the workflow (`await handle.signal(LoadWorkflow.on_tracking_ping, payload)`). Buffered by the server, delivered to the workflow's handler in order.
- **Signal-with-Start**: atomically starts the workflow if it doesn't exist and delivers the signal, or just delivers the signal if it does. In Python: `client.start_workflow(LoadWorkflow.run, ..., id="load-123", start_signal="on_event", start_signal_args=[event])`. **This is the primitive you want for `POST /events/*` — it makes the API endpoint idempotent and removes the "does the workflow exist yet?" branch from your code.**
- **Queries**: synchronous, read-only inspection of workflow state (good for `GET /loads/{id}/status`).
- **Updates**: synchronous request/response into the workflow with validators — useful if `POST /submit-task` needs to return a result instead of fire-and-forget.
- **Durable Timers**: `await asyncio.sleep(seconds)` inside a workflow becomes a server-persisted timer. Per `docs.temporal.io/develop/python/timers`: "A Workflow can sleep for months. Timers are persisted, so even if your Worker or Temporal Service is down when the time period completes, as soon as your Worker and Temporal Service are back up, the sleep() call will resolve and your code will continue executing."

### 8. Testing: time-skipping makes the eval harness fast
The Python SDK ships `temporalio.testing.WorkflowEnvironment.start_time_skipping()`, which lazily downloads an in-memory test server binary that fast-forwards its clock whenever no work is pending. A workflow that calls `await asyncio.sleep(24*60*60)` completes in milliseconds in tests. Activities can be mocked via `ActivityEnvironment` or by registering mock activity functions on the test worker. For end-to-end local runs, `temporal server start-dev` starts a full single-binary server + Web UI on `localhost:7233` and `localhost:8233` (in-memory by default, `--db-filename` for persistence).

### 9. Terraform support
The official **`temporalio/temporalcloud`** provider on the Terraform Registry manages namespaces, users, service accounts, API keys, and Nexus endpoints declaratively. A namespace creation is ~10 lines of HCL:

```hcl
terraform {
  required_providers { temporalcloud = { source = "temporalio/temporalcloud" } }
}
provider "temporalcloud" {} # reads TEMPORAL_CLOUD_API_KEY env var

resource "temporalcloud_namespace" "fh" {
  name           = "freight-watchtower-dev"
  regions        = ["aws-us-east-1"]
  retention_days = 14
  api_key_auth   = true
}
```

AWS resources (ECR repo, ECS cluster, Fargate task definition, IAM roles, Secrets Manager secret holding the Temporal API key) use the standard `hashicorp/aws` provider. The reference repo [`papnori/temporal-ecs-terraform`](https://github.com/papnori/temporal-ecs-terraform) and the companion repo [`temporal-community/temporal-ecs`](https://github.com/temporal-community/temporal-ecs) are publishable starting points.

---

## Details

### How Temporal maps onto FreightHero Watchtower

| Requirement | Temporal mapping |
|---|---|
| API decoupled from agent execution | FastAPI calls `client.start_workflow(...)` / `handle.signal(...)`; Worker pool consumes from Temporal Task Queue |
| Per-load state outside process memory | Workflow Event History persisted in Temporal Cloud; in-workflow `self.state` survives crashes via replay |
| Events for same load isolated under concurrency | `workflow_id = f"load-{load_id}"` — server enforces singleton, single-threaded message loop |
| Timers / scheduled follow-ups | `await asyncio.sleep(timedelta(...))` inside the workflow |
| Containerized | Docker — same image runs FastAPI + Worker |
| Deployed via Terraform | `hashicorp/aws` + `temporalio/temporalcloud` for the namespace |

**Concrete code shape:**

```python
@workflow.defn
class LoadWorkflow:
    def __init__(self):
        self.state = {"events": [], "status": "new"}
        self.pending = asyncio.Queue()

    @workflow.signal
    async def on_event(self, event: dict):
        await self.pending.put(event)

    @workflow.query
    def get_state(self) -> dict:
        return self.state

    @workflow.run
    async def run(self, load_id: str):
        while True:
            try:
                event = await asyncio.wait_for(
                    self.pending.get(),
                    timeout=24 * 3600,   # durable timer
                )
                decision = await workflow.execute_activity(
                    run_agent,
                    args=[self.state, event],
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )
                self.state = apply_decision(self.state, decision)
            except asyncio.TimeoutError:
                await workflow.execute_activity(
                    check_eta, self.state["load_id"],
                    start_to_close_timeout=timedelta(seconds=30),
                )
```

The FastAPI shim shrinks to a handful of lines per route:

```python
@app.post("/events/{load_id}")
async def post_event(load_id: str, event: dict):
    handle = await temporal_client.start_workflow(
        LoadWorkflow.run, load_id,
        id=f"load-{load_id}",
        task_queue="freight-watchtower",
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        start_signal="on_event",
        start_signal_args=[event],
    )
    return {"workflow_id": handle.id}
```

### Where to run the Worker process

| Option | Pros | Cons | Recommendation |
|---|---|---|---|
| **AWS ECS Fargate** | First-class Terraform support; official Temporal blog guide & reference repo; matches "real cloud account" rubric | VPC, NAT/egress, IAM roles add ~150 lines of HCL | **Pick this if Terraform-on-AWS is explicitly graded** |
| AWS App Runner | Simpler than ECS; one resource | Designed for HTTP services that scale on requests — Workers don't take inbound traffic, so scaling won't behave as designed | Workable but awkward |
| Single EC2 + systemd | Cheapest, simplest IaC | Manual patching, no auto-recovery | Acceptable for a demo; weak engineering signal |
| Fly.io | Dead-simple `fly deploy`; egress-only is fine | Not AWS — may not satisfy "real cloud account" rubric | Pick if the rubric says "any cloud" |
| docker-compose | Local dev / eval harness only | Not deployable | Use for `make dev` |

The cleanest "one-week" answer for an AWS rubric: a single Fargate task definition built from one Docker image, with two ECS services using different container commands — one running `uvicorn api:app` (behind an ALB) and one running `python -m worker` (no load balancer, egress-only SG). The Temporal Cloud namespace is provisioned via the `temporalcloud` Terraform provider; the API key lives in AWS Secrets Manager and is injected into the task via the ECS `secrets` block.

### Honest tradeoffs

- **Determinism constraint**: Workflow code must be deterministic — no `random`, no `datetime.now()`, no direct HTTP calls inside `@workflow.defn` methods. All non-determinism goes in Activities. The Python SDK sandbox enforces this aggressively at import time. This is a real learning curve, but for SOP-driven freight logic it's a natural fit because the "decide" step naturally belongs in an activity (LLM call).
- **Action billing**: every signal, timer fire, activity start, and workflow start is a billable "Action." For a take-home you will never approach the $1,000 trial credit, but be aware that hyperactive polling-as-timers patterns can rack up actions in production.
- **Vendor lock-in is mild**: the same Workflow/Activity code runs on self-hosted Temporal. If the reviewer hates managed services, you can swap to `temporal server start-dev` for the local demo with zero code changes — only the `Client.connect` URL changes.
- **You commit to gRPC egress**: your Worker container must be able to reach `*.tmprl.cloud:7233`. In a default-VPC ECS Fargate setup this just works; in a locked-down VPC you'd need a NAT Gateway or AWS PrivateLink (Temporal Cloud supports PrivateLink on higher tiers).

---

## Recommendations

**Stage 1 — Hour 0–4: Local skeleton**
1. `pip install temporalio fastapi uvicorn`.
2. Install Temporal CLI; run `temporal server start-dev`.
3. Write `LoadWorkflow` with one signal (`on_event`), one query (`get_state`), one activity (`run_agent` that calls your LLM). Run it locally; confirm it works in the Temporal Web UI at `localhost:8233`.
4. Write the FastAPI shim with three endpoints; verify `POST /events/{load_id}` starts/signals via `signal_with_start`.

**Stage 2 — Hour 4–8: Tests**
1. Add `pytest` + `pytest-asyncio` and a fixture that uses `WorkflowEnvironment.start_time_skipping()`.
2. Write one test that demonstrates a 24-hour ETA follow-up firing without real elapsed time. This is the highest-leverage demo of "I understand the framework choice" you can show a reviewer.

**Stage 3 — Hour 8–16: Cloud + IaC**
1. Sign up at `cloud.temporal.io`, claim the $1,000 trial credit, create a namespace with **API key auth** named `freight-watchtower-dev`.
2. Write `main.tf` with two providers (`temporalio/temporalcloud`, `hashicorp/aws`). Either import the manually-created namespace into Terraform state, or destroy it and re-create from HCL — the provider supports both.
3. Build the Docker image; push to ECR; deploy two ECS Fargate services from the [`temporal-community/temporal-ecs`](https://github.com/temporal-community/temporal-ecs) template (one for the Worker, one for FastAPI behind an ALB).
4. Store the Temporal API key in AWS Secrets Manager; reference it from the ECS task definition's `secrets` block.

**Stage 4 — Hour 16–24: Polish**
1. Add a Query handler for `GET /loads/{id}/status`.
2. Set Activity `RetryPolicy` with sensible bounds; demonstrate an LLM-call failure that retries.
3. Record a short Loom showing: POST event → workflow visible in Temporal Cloud UI → timer scheduled → time-skip test passes in <1s.

**Benchmarks that would change the recommendation:**
- **If signup at `cloud.temporal.io` is blocked by your email domain or namespace provisioning stalls >30 minutes** → fall back to `temporal server start-dev` in a docker-compose, deploy that compose file to a single EC2 instance, and document it as "self-hosted, dev-mode" with a clear migration path to Cloud (the `Client.connect` URL is the only change).
- **If the rubric explicitly forbids third-party SaaS dependencies** → run Temporal server in a sidecar container with the SQLite-backed dev binary (`temporal server start-dev --db-filename /data/temporal.db` on an EBS volume). This is not production-grade but is honest for a one-week demo and avoids Cassandra/Elasticsearch entirely.
- **If graph-shaped agent control flow is genuinely core to the deliverable** → use the official `temporalio.contrib.langgraph_plugin` sample to host LangGraph inside an activity. Otherwise drop LangGraph; a single "decide" activity that calls the LLM with the load state is simpler and easier for a reviewer to read.

---

## Caveats

- **Pricing changed in early 2025**: Temporal restructured to "Essentials / Business / Enterprise / Mission Critical" plans. Per the official pricing docs, "The Essentials tier is priced at the greater of $100/month or 5% of your Temporal Cloud consumption. The Business tier is priced at the greater of $500/month or 10% of Temporal Cloud consumption." Older third-party blog posts cite "$200/month Growth" or "free Dev tier" — those tiers no longer exist for new signups. The $1,000 promotional credit is the relevant figure for a one-week take-home.
- **mTLS vs API key**: the Temporal docs nudge new users toward API keys ("API keys are generally easier to manage than mTLS certs if you're not using certificate management infrastructure otherwise"); the Terraform Cloud provider and Cloud Ops API only support API key auth, which is another reason to pick it.
- **Determinism gotchas**: importing libraries like `requests` or `openai` from inside a workflow file is permitted (the SDK sandbox passes them through), but *calling* their I/O functions from workflow code (rather than from an activity) will break replay. This trips up everyone the first time. Keep all I/O inside `@activity.defn` functions. The SDK learning curve is real but modest for a Python developer comfortable with `asyncio`; no authoritative timeline figure is published.
- **One conflicting description**: the docs describe the time-skipping test server as "an in-memory implementation of Temporal Server that supports skipping time," while the Python SDK README clarifies it's a separate binary (lazily downloaded, derived from the Java SDK compiled via GraalVM). Both are correct, but the Python time-skipping server "does not work on ARM" natively — on Apple Silicon it runs the x64 binary under Rosetta. If your tests hang on an M-series Mac, install Rosetta or fall back to `start_local()`.
- **Workflow ID is not a secret**: per the docs, "Do not include sensitive data, secrets, or personally identifiable information (PII) as a Workflow Id. Workflow Ids are stored in plain text, are not processed by a custom Payload Codec, and are visible in the Temporal Web UI, CLI output, Event History, and system logs." Use `load-{uuid}` not `load-{customer_email}`.
- **One unverified figure I considered citing and dropped**: the often-repeated "2–4 weeks to onboard engineers to Temporal's programming model" appears only in third-party marketing/comparison articles; no Temporal documentation source confirms it. Treat any onboarding-time estimate as anecdotal.