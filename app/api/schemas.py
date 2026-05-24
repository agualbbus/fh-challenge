"""Pydantic models translated from challenge-input.schema.json."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

CustomerId = Literal["customer_a", "customer_b", "customer_c"]
LoadState = Literal["on_route_to_delivery", "at_delivery", "delivered", "pod_collected"]
TaskInstructionType = Literal["delivery_eta_checkpoint", "confirm_delivery"]
Channel = Literal["sms", "email"]
SenderType = Literal[
    "driver", "dispatcher", "carrier", "broker", "shipper", "hero", "tool", "other"
]


class Company(BaseModel):
    name: str
    uuid: str | None = None


class PersonContact(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    uuid: str | None = None


class Address(BaseModel):
    line_1: str
    line_2: str | None = None
    city: str
    state: str
    postal_code: str
    country: str


class Appointment(BaseModel):
    type: Literal["fixed", "window", "fcfs"]
    start_utc: datetime | None = None
    end_utc: datetime | None = None
    timezone: str


class Coordinates(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class Stop(BaseModel):
    stop_id: str
    type: Literal["pickup", "delivery"]
    status: str | None = None
    address: Address
    appointment: Appointment
    coordinates: Coordinates
    reference_numbers: dict[str, str | None] = Field(default_factory=dict)


class LoadData(BaseModel):
    external_load_id: str
    po_number: str | None = None
    instructions: str | None = None
    companies: dict[str, Company]
    contacts: dict[str, PersonContact] = Field(default_factory=dict)
    stops: list[Stop]

    model_config = {"extra": "allow"}


class LoadSeedRequest(BaseModel):
    load_id: str
    customer_id: CustomerId
    load_data: LoadData
    initial_state: LoadState | None = None


class SubmitTaskRequest(BaseModel):
    task_uuid: str
    load_id: str
    customer_id: CustomerId
    task_instruction_type: TaskInstructionType
    requested_at: datetime
    source: Literal["api", "operator", "system"] | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class Attachment(BaseModel):
    attachment_id: str
    file_name: str
    mime_type: str | None = None
    mock_classification: dict[str, Any]


class InboundCommunication(BaseModel):
    channel: Channel
    sender_type: SenderType
    sender_name: str | None = None
    content: str
    attachments: list[Attachment] = Field(default_factory=list)


class InboundCommunicationEvent(BaseModel):
    event_id: str
    event_type: Literal["inbound_communication"] = "inbound_communication"
    load_id: str
    customer_id: CustomerId
    occurred_at: datetime
    inbound_communication: InboundCommunication


class TrackingPing(BaseModel):
    tracking_id: str
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    distance_to_delivery_miles: float = Field(ge=0)
    ping_sequence: int = Field(ge=1)
    provider: str | None = None


class TrackingEvent(BaseModel):
    event_id: str
    event_type: Literal["tracking"] = "tracking"
    load_id: str
    customer_id: CustomerId
    occurred_at: datetime
    tracking: TrackingPing


class LoadUpdatePayload(BaseModel):
    milestone_state: LoadState | None = None
    load_data_patch: dict[str, Any] | None = None
    reason: str | None = None


class LoadUpdateEvent(BaseModel):
    event_id: str
    event_type: Literal["load_update"] = "load_update"
    load_id: str
    customer_id: CustomerId
    occurred_at: datetime
    load_update: LoadUpdatePayload


class AcceptedResponse(BaseModel):
    accepted: bool = True
    load_id: str
    workflow_id: str
