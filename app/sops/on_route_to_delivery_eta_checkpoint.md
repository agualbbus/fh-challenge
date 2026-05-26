# SOP: On Route to Delivery / ETA Checkpoint

## Purpose

Use this SOP when a load is on route to delivery. The goal is to keep the delivery ETA accurate, identify arrival at the receiver, answer basic load questions, and surface operational risk without creating unnecessary noise.

## Operating Principles

- Apply the relevant customer expectations for this load.
- Match the driver's inbound channel for driver-facing replies unless the customer workflow says otherwise.
- Keep driver-facing messages short, specific, and operational.
- Do not invent missing load information.
- Ignore broker-originated inbound messages in this challenge.
- Leave a clear reason for the selected branch.

## Customer-Specific Expectations

This SOP describes the shared on-route workflow. When a customer-specific SOP or expectation changes timing, wording, escalation, visibility, or document handling, apply the customer-specific expectation for the load.

## Event Routing

1. If the event is a tracking ping, follow [Tracking Ping Handling](#tracking-ping-handling).
2. If the event is inbound communication, identify the sender, channel, message content, and attachments.
3. If the sender is the broker, follow [Broker Messages](#broker-messages).
4. If the message indicates arrival, follow [Arrival Confirmation](#arrival-confirmation).
5. If the message provides ETA, follow [Driver Provides ETA](#driver-provides-eta).
6. If the message asks for load information, follow [Load Information Question](#load-information-question).
7. If the message reports operational trouble, follow [Operational Issue](#operational-issue).
8. Otherwise, acknowledge only when the driver clearly expects a response.

## Tracking Ping Handling

Use when the event contains GPS/tracking data.

Expected behavior:

1. Determine whether the ping is fresh based on its timestamp.
2. Compare the provided distance to delivery against the customer's delivery geofence.
3. If tracking is stale, keep the load on route to delivery and continue the customer's ETA follow-up process.
4. If tracking is fresh but outside the geofence, keep the load on route to delivery.
5. If there are three consecutive fresh pings inside the delivery geofence, treat the driver as arrived at delivery and begin confirm delivery handling.

## Arrival Confirmation

Use when a driver, dispatcher, or carrier says they arrived or are at delivery, especially when tracking is missing or stale.

Examples:

- "arrived"
- "I'm here"
- "at receiver"
- "checked in at delivery"

Expected behavior:

1. Call `update_load_state(target_state="at_delivery")` to mark the load as arrived.
2. Call `cancel_timers()` to stop all ETA follow-up pressure.
3. Reply to the driver on the same inbound channel using the customer's `first_arrival_message` (the message contains instructions about POD — do not invent different wording).
4. Do not create issues or tasks unless the driver reports a separate problem alongside the arrival.

## Driver Provides ETA

Use when the driver, dispatcher, or carrier provides a delivery ETA.

Examples:

- "ETA 3pm"
- "I'll be there at 14:30"
- "delivery ETA is 6:15 tonight"

Expected behavior:

1. Interpret the ETA using the delivery stop timezone.
2. Call `validate_eta` to confirm it is plausible for the delivery appointment.
3. If the ETA is usable: call `update_eta(target_location="delivery", eta_utc=<iso>)`, then acknowledge the driver on the same channel with a short message that includes the word **updated** (e.g. "Got it — ETA updated"), then call `create_timer(timer_type="eta_followup", fire_at_utc=<now + eta_followup_minutes>)` to schedule the next follow-up check.
4. If the ETA is ambiguous, ask one short clarification question when the driver can reasonably answer it.
5. If the ETA indicates a meaningful service risk, treat it as a delivery delay and make it visible to the operations team according to the customer workflow.

## Load Information Question

Use when the driver asks for delivery address, appointment time, reference number, receiver contact, pickup/delivery number, or similar load information.

Expected behavior:

1. Look for the requested information in the known load data.
2. If the information is available, reply on the same channel with only the requested information.
3. If the information is missing, reply on the same channel acknowledging that the team is **checking** on it, then follow the customer's missing-information workflow for human follow-up and any required visibility (task creation, slack audience).

## Operational Issue

Use when the sender reports a problem that can affect delivery.

Examples:

- truck broke down;
- accident;
- flat tire;
- facility cannot receive;
- driver is blocked at gate;
- freight damage.

Expected behavior:

1. Treat the message as an operational exception that needs operations-team attention.
2. Use the most specific issue category that fits the message.
3. If the driver sent the message by SMS, acknowledge briefly on the same channel — the reply must include the word **review** (e.g. "the team will review and follow up").
4. Do not give long troubleshooting advice.

## Broker Messages

Broker-originated inbound messages are ignored in this challenge.

Expected behavior:

1. Do not reply.
2. Do not process attachments or delivery updates from the broker message.
3. Record the reason for taking no action.

## No Action

Use when the message is a thank-you, duplicate, automated non-human notification, or irrelevant broker/shipper conversation.

Expected behavior:

1. Take no external action.
2. Record the reason for no action for later review.
