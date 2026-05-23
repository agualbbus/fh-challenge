# Customer Expectations

These profiles describe the behavior differences the implementation must support for visible tests and likely hidden variants. They are intentionally not provided as a machine-ready configuration file. Choose an approach that makes these differences maintainable, testable, and easy to extend.

## Behavior Matrix

| Area | Customer A | Customer B | Customer C |
| --- | --- | --- | --- |
| Escalation channel | Email | Slack-style internal/customer notification | Both email and Slack-style notification |
| Missing load info | Create a human task | Create a human task and send configured visibility notification | Create a human task |
| POD validation | Automatic when `check_attachment` returns `document_pod` | Human review task when POD is received | Automatic when `check_attachment` returns `document_pod` |
| POD received visibility | Notify through escalation channel when POD is received | No broker/customer visibility notification | No broker/customer visibility notification |
| Delivered without POD visibility | Notify through escalation channel | No broker/customer visibility notification | Notify through escalation channel |
| Delivery geofence radius | 1 mile | 2 miles | 3 miles |
| ETA follow-up timer | 30 minutes | 60 minutes | 45 minutes |
| Lumper receipt handling | Classify attachment if present and create review task | Classify attachment if present and create review task | If an email attachment is classified as a lumper receipt, forward the email and attachment to the broker's special email; otherwise create lumper review task and make sure POD handling is not skipped |
| First arrival message | Ask for unloading status and POD when available | Ask driver to confirm unloading start and send POD when empty | Ask for unloading updates, POD, and any lumper receipt when available |

## Communication Guardrails

| Rule | Expected behavior |
| --- | --- |
| Driver-facing replies | Match the inbound channel unless a SOP branch explicitly says otherwise. |
| Message length | Keep replies short, operational, and specific to the SOP branch. |
| Missing information | Do not make up addresses, appointment times, reference numbers, contacts, payment status, or policies. |
| Broker messages | Ignore broker-originated inbound messages in this challenge. Do not reply and do not use them as action triggers. |
| Identity/reference style | Use generic broker/customer references unless the seeded load data explicitly provides a name needed for the response. |
| Scope control | Do not offer general help outside the SOP. Stick to the workflow action needed for the event. |
