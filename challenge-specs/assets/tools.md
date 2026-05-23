# Mock Tool Contracts

Tools are mocked. They should still behave like production integration boundaries:

- validate inputs;
- return structured results;
- append a durable tool-call record;
- include `load_id`, `event_id`, and timestamp;
- be usable in eval assertions.

## Tool Call Record

Every tool call should be recorded in this shape or a clearly documented equivalent:

```json
{
  "tool_call_id": "tool-call-uuid",
  "event_id": "event-123",
  "load_id": "load-123",
  "tool": "send_sms",
  "arguments": {},
  "result": {},
  "created_at": "2026-05-11T15:00:00Z"
}
```

## Communication Tools

### `send_sms`

Send an SMS-style message to the driver or dispatcher.

Required arguments:

- `recipient`: `driver` or `dispatcher`
- `message`: short text

Expected result:

```json
{ "ok": true, "channel": "sms", "message_id": "sms-uuid" }
```

### `send_email`

Send or reply to an operational email thread, usually with the carrier team or dispatcher.

Required arguments:

- `recipient`: `driver`, `dispatcher`, `carrier_team`, `main_thread`, or explicit email
- `subject`: text
- `body`: text

Expected result:

```json
{ "ok": true, "channel": "email", "message_id": "email-uuid" }
```

### `forward_email`

Forward the current email and its attachments to a broker-provided special email address. Use this for forwarding documents as-is, not for composing an operational message to the carrier team.

Required arguments:

- none

Expected result:

```json
{ "ok": true, "channel": "email", "message_id": "forwarded-email-uuid" }
```

### `send_slack_message`

Send internal or broker-visible Slack-style notification.

Required arguments:

- `audience`: `internal`, `broker`, or `customer`
- `message`: text
- `escalation_type`: optional string

Expected result:

```json
{ "ok": true, "channel": "slack", "message_id": "slack-uuid" }
```

## Attachment Tool

### `check_attachment`

Classify one attachment using the fixture-provided metadata.

Required arguments:

- `attachment_id`

Expected result:

```json
{
  "ok": true,
  "attachment_id": "att-pod-1",
  "categories": ["document_pod"],
  "description": "Signed delivery document"
}
```

Recognized categories:

- `document_pod`
- `lumper_receipt`
- `other`

## Load State Tools

### `update_load_state`

Update the load milestone.

Required arguments:

- `target_state`: one of `on_route_to_delivery`, `at_delivery`, `delivered`, `pod_collected`
- `reason`: short text

Expected result:

```json
{ "ok": true, "previous_state": "on_route_to_delivery", "new_state": "at_delivery" }
```

### `update_eta`

Store a driver-provided ETA.

Required arguments:

- `target_location`: `delivery`
- `eta_utc`: ISO timestamp
- `source`: `driver`, `dispatcher`, `carrier`, or `system`

Expected result:

```json
{ "ok": true, "target_location": "delivery", "eta_utc": "2026-05-11T19:00:00Z" }
```

## Timer Tools

### `create_timer`

Create a follow-up timer.

Required arguments:

- `timer_type`: `eta_followup`, `pod_followup`, `delivery_status_followup`, or `attachment_clarification`
- `fire_at_utc`: ISO timestamp
- `reason`: short text

Expected result:

```json
{ "ok": true, "timer_id": "timer-uuid" }
```

### `cancel_timer`

Cancel one timer.

Required arguments:

- `timer_id`

### `cancel_timers`

Cancel timers by type or all timers for a load.

Required arguments:

- `timer_type`: optional string

## Human Work Tools

### `create_task`

Create a non-urgent human follow-up task.

Required arguments:

- `title`
- `description`
- `task_type`: `missing_load_info`, `pod_review`, `lumper_review`, `manual_followup`, or `other`

Expected result:

```json
{ "ok": true, "task_id": "task-uuid" }
```

### `create_issue`

Create an urgent operational issue.

Required arguments:

- `title`
- `description`
- `issue_type`: `equipment_failure`, `delivery_delay`, `facility_problem`, or `other`

Expected result:

```json
{ "ok": true, "issue_id": "issue-uuid" }
```

## Helper Tools

### `get_load_info`

Read a specific field or section from the persisted load data.

Required arguments:

- `field`: short string such as `delivery_address`, `receiver_phone`, `delivery_reference`, or `driver_contact`

Expected result:

```json
{ "ok": true, "field": "delivery_address", "value": "456 Delivery St, Dallas, TX 75201" }
```

If the value is missing:

```json
{ "ok": false, "field": "receiver_phone", "error": "missing" }
```

### `validate_eta`

Validate and normalize a driver-provided ETA against the delivery appointment and timezone.

Required arguments:

- `raw_eta`: text from the inbound message
- `delivery_timezone`: IANA timezone string

Expected result:

```json
{ "ok": true, "eta_utc": "2026-05-11T19:30:00Z", "is_plausible": true }
```

### `get_appointment_time`

Return the appointment time for a stop.

Required arguments:

- `stop_type`: `pickup` or `delivery`

Expected result:

```json
{
  "ok": true,
  "stop_type": "delivery",
  "appointment": {
    "type": "fixed",
    "start_utc": "2026-05-11T20:00:00Z",
    "timezone": "America/Chicago"
  }
}
```

You may add other helper tools if useful, but document them.

Hidden evals will focus on observable state transitions and required/forbidden tool calls, not on exact internal helper names.
