# Background: Freight Agent Concepts

## Freight Roles

- **Broker**: FreightHero's customer. The broker owns the customer relationship and needs visibility when a load is at risk.
- **Shipper**: The company shipping the freight. It is usually the broker's customer.
- **Carrier**: The trucking company moving the freight.
- **Dispatcher**: A carrier-side operator who coordinates the driver.
- **Driver**: The person operating the truck.
- **Hero**: A FreightHero human operator. Create a task when a human should review or follow up.
- **Robin**: The AI agent. Robin should follow the SOP, use tools, and avoid making promises or approvals.

## Load Lifecycle

A load is a shipment with pickup and delivery stops. This challenge focuses on the late lifecycle:

1. Driver has departed pickup.
2. Driver is **on route to delivery**.
3. Driver arrives at delivery.
4. Driver unloads.
5. Driver sends Proof of Delivery.
6. Load is delivered or POD collected.

Useful milestone states:

- `on_route_to_delivery`
- `at_delivery`
- `delivered`
- `pod_collected`

## ETA Checkpoint

The ETA checkpoint workflow monitors the load while the driver is on route to delivery.

Typical inputs:

- inbound SMS/email from driver, dispatcher, carrier, broker, or automated sender;
- tracking pings from GPS/tracking providers;
- load updates from a system of record.

Typical outcomes:

- update ETA;
- ask driver for ETA;
- acknowledge useful driver updates;
- create task for missing information;
- create issue for operational failures;
- update state to `at_delivery` when arrival is confirmed;
- ignore broker-side business chatter.

## Confirm Delivery

The confirm delivery workflow starts when the driver is at delivery or likely at delivery.

Typical outcomes:

- send a first arrival message asking for unloading status and POD;
- ask for updates if unloading has not started;
- update state when unloaded or delivered;
- check attachments for POD, receipt, or other document type;
- create a task or escalation depending on customer POD policy;
- schedule follow-ups.

## POD, BOL, and Attachments

**POD** means Proof of Delivery. It is the signed document confirming freight was delivered.

**BOL** means Bill of Lading. In delivery context, a signed BOL can function as POD. For this challenge, if `check_attachment` returns category `pod` or `document_pod`, treat it as POD.

**Lumper receipt** means a receipt for unloading labor or facility fees. It may require separate receipt review.

You do not need real computer vision. The fixture events provide attachment metadata, and your mocked `check_attachment` tool should return the provided categories.

## Human Follow-Up and Issues

Issues are operational problems that can affect service:

- truck breakdown;
- accident;
- facility access problem;
- damaged freight.

Use **task** for human follow-up that is not immediately operationally critical. Use **issue** for urgent operational problems.

## Tracking and Geofences

Tracking pings include latitude, longitude, timestamp, and distance to the delivery stop.

For this challenge:

- customer-specific rules define delivery geofence radius: 1, 2, or 3 miles;
- 3 consecutive fresh pings inside the delivery geofence confirm arrival;
- a driver text saying "arrived" can also confirm arrival when tracking is missing or stale;
- after arrival, the load should move toward the confirm delivery workflow.

## Timers

Timers represent follow-up work that should happen later.

Examples:

- ask for ETA again in 30, 45, or 60 minutes;
- follow up for POD after delivery;
- clarify ambiguous attachment after 30 minutes.

Timers can be implemented using a job table, delayed queue, cloud scheduler, or a documented simulation as long as it is testable.

In production, these are real scheduled events that re-enter the agent workflow later. They are separate from submitted workflow tasks and should not be modeled as a `task_instruction_type`. For this challenge, it is up to you to decide how to design and implement timers. The important capability is that the agent can handle follow-ups according to each customer SOP.

## Customer-Specific Rules

Different customers want different behavior. This is a core part of the challenge.

Examples:

- email vs Slack escalation;
- automatic POD validation vs human review;
- different geofence radius;
- different first arrival message;
- different ETA follow-up timer;
- lumper receipt handling;
- whether POD received should trigger broker visibility.

Do not hardcode these differences inside one-off branches. The visible fixtures include three customer profiles. Hidden tests may vary customer behavior.

## Communication Rules

- Refer to the broker by name only when the SOP or customer-specific rules ask for it.
- Match the inbound channel for driver-facing replies unless the SOP says otherwise.
- Keep driver-facing messages short and operational.
- Do not make up missing load information.
- Do not approve payments or detention claims.
- Do not reveal internal reasoning, tooling, queue mechanics, or scoring.
- Broker messages must be ignored.
