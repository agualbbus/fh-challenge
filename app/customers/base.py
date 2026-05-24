"""Customer profile loader — Pydantic models from YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

CUSTOMERS_DIR = Path(__file__).resolve().parent


class EscalationConfig(BaseModel):
    channels: list[Literal["email", "slack"]]


class PodConfig(BaseModel):
    validation: Literal["automatic", "human_review"]
    notify_on_received: bool
    notify_delivered_without_pod: bool


class MissingLoadInfoConfig(BaseModel):
    create_task: bool
    notify_slack: bool = False
    slack_audience: Literal["internal", "broker", "customer"] = "broker"


class LumperConfig(BaseModel):
    mode: Literal["review_task", "forward_email"]


class CustomerProfile(BaseModel):
    customer_id: Literal["customer_a", "customer_b", "customer_c"]
    escalation: EscalationConfig
    geofence_radius_miles: float
    eta_followup_minutes: int
    pod: PodConfig
    missing_load_info: MissingLoadInfoConfig
    lumper: LumperConfig
    first_arrival_message_key: str


_profiles: dict[str, CustomerProfile] | None = None


def _load_profiles() -> dict[str, CustomerProfile]:
    profiles: dict[str, CustomerProfile] = {}
    for path in sorted(CUSTOMERS_DIR.glob("customer_*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        profile = CustomerProfile.model_validate(data)
        profiles[profile.customer_id] = profile
    if len(profiles) != 3:
        raise RuntimeError(f"Expected 3 customer profiles, found {len(profiles)}")
    return profiles


def get_customer_profiles() -> dict[str, CustomerProfile]:
    global _profiles
    if _profiles is None:
        _profiles = _load_profiles()
    return _profiles


def get_customer_profile(customer_id: str) -> CustomerProfile:
    profiles = get_customer_profiles()
    if customer_id not in profiles:
        raise KeyError(f"Unknown customer_id: {customer_id}")
    return profiles[customer_id]
