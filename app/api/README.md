# Postman collection

`FreightHero-Watchtower.postman_collection.json` — import into Postman.

## Collection variables

| Var | Default | Notes |
| --- | --- | --- |
| `baseUrl` | live ALB | swap to `http://localhost:8000` for local |
| `apiKey` | *(empty)* | put `API_KEY` from AWS Secrets Manager `freight-watchtower/app` |

Collection auth = API key in `X-API-Key` header (applied to every request except the two negative tests and `/health`).

## Requests

- **Health (no auth)** — `GET /health`, reports SQS + Postgres reachability.
- **Seed Load** — `POST /loads`, seeds `load-visible-001` from the eval fixture.
- **Submit Task** — `POST /submit-task`, `delivery_eta_checkpoint` example.
- **Event - Inbound Communication** — `POST /events/inbound-communication`, driver SMS example.
- **Event - Tracking** — `POST /events/tracking`.
- **Event - Load Update** — `POST /events/load-update`, milestone change.
- **Auth - Missing key (expect 401)** / **Auth - Wrong key (expect 401)** — negative tests.

All write endpoints return `202 Accepted` with `{accepted, load_id, workflow_id}` — the work is published to SQS and processed asynchronously by the worker.
