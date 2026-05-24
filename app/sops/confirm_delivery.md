# SOP: Confirm Delivery

## Purpose

Use this SOP when a load is at delivery or when another workflow hands off a likely delivery arrival or POD event. The goal is to confirm unloading, collect or validate Proof of Delivery, handle lumper receipts when relevant, and escalate only when customer expectations require human review or visibility.

## Operating Principles

- Apply the relevant customer expectations for this load.
- Match the inbound channel when replying to a driver, dispatcher, or carrier.
- Keep driver-facing messages short and operational.
- Do not assume an attachment is POD unless it has been classified as POD or the input is explicitly trusted.
- Do not ask for POD again when valid POD was already received in the same event.
- Do not approve lumper or detention payment.
- Ignore broker-originated inbound messages in this challenge.
- Leave a clear reason for the selected branch, attachment classification, and outcome.

## Event Routing

1. If the sender is the broker, follow [Broker Messages](#broker-messages).
2. If the message contains attachments, follow [Attachment Handling](#attachment-handling).
3. If the sender says unloading started but is not finished, follow [Unloading Started](#unloading-started).
4. If the sender says unloading has not started, follow [Unloading Not Started](#unloading-not-started).
5. If the sender confirms unloaded, empty, delivered, or done without POD, follow [Delivery Confirmed Without POD](#delivery-confirmed-without-pod).
6. If the sender asks load-information questions, use the matching behavior from the ETA checkpoint SOP.
7. If the sender reports a delivery-impacting problem, follow [Operational Issue](#operational-issue).
8. Otherwise, take no action or send a short acknowledgment only if the driver clearly expects a response.

## First Arrival Contact

Use when the workflow starts because the driver arrived, or when the system needs first contact at delivery.

Expected behavior:

1. Follow the customer's first-arrival acknowledgement and delivery-status follow-up workflow.
2. Do not mention detention unless the driver asked about it.

## Attachment Handling

Use when the message includes one or more delivery-related attachments.

### POD Document

Use when an attachment is classified as POD or signed delivery paperwork.

Expected behavior:

1. Follow the customer's POD receipt acknowledgement, validation, status transition, visibility, and follow-up rules.

### Lumper Receipt

Use when an attachment is classified as a lumper receipt.

Expected behavior:

1. Record that a lumper receipt was received.
2. Follow the customer's lumper receipt review and visibility rules.
3. If POD is also present, handle POD first and avoid duplicate delivery-state changes.
4. Do not approve reimbursement.

### Other or Unreadable Attachment

Use when the attachment is unrelated, unreadable, or not enough to confirm delivery.

Expected behavior:

1. If the message suggests delivery is complete, ask for a clear POD.
2. If delivery status is unclear, ask for unloading status.
3. Do not treat the load as POD collected.

## Unloading Started

Use when the sender says unloading has begun but is not complete.

Expected behavior:

1. Thank the sender and ask them to send POD when unloaded.
2. Continue delivery-status follow-up.
3. Follow the customer's visibility rules for this status.

## Unloading Not Started

Use when the sender says they are checked in, waiting, in line, or not unloading yet.

Expected behavior:

1. Acknowledge and ask for an update when unloading starts or finishes.
2. Do not treat unrelated attachments as POD when the text clearly says unloading has not started.
3. Continue delivery-status follow-up.

## Delivery Confirmed Without POD

Use when the sender says unloaded, empty, MT, done, delivered, or similar but no POD is provided.

Expected behavior:

1. Treat the load as delivered or likely delivered.
2. Ask for POD.
3. Continue POD follow-up.
4. Follow the customer's visibility rules for this scenario.

## Broker Messages

Broker-originated inbound messages are ignored in this challenge.

Expected behavior:

1. Do not reply.
2. Do not process attachments or delivery updates from the broker message.
3. Record the reason for taking no action.

## Operational Issue

Use when the sender reports damage, facility problems, inability to unload, or another delivery-impacting problem.

Expected behavior:

1. Treat the message as an operational exception that needs operations-team attention.
2. Acknowledge briefly if the sender is a driver, dispatcher, or carrier and clearly expects a response.
3. Do not treat the load as delivered or POD collected unless there is a separate clear delivery or POD signal.

## Completion Criteria

The confirm delivery workflow is complete when one of these is true:

- POD is collected;
- delivery is confirmed and any required human document review is open.
