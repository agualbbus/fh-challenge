"""Customer profile loader — Pydantic models from YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

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
    review_task_fallback: bool = False
    enforce_pod_handling: bool = True


class CustomerProfile(BaseModel):
    customer_id: str
    escalation: EscalationConfig
    geofence_radius_miles: float
    eta_followup_minutes: int
    pod: PodConfig
    missing_load_info: MissingLoadInfoConfig
    lumper: LumperConfig
    first_arrival_message: str


_profiles: dict[str, CustomerProfile] | None = None


def _load_profiles() -> dict[str, CustomerProfile]:
    profiles: dict[str, CustomerProfile] = {}
    for path in sorted(CUSTOMERS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        profile = CustomerProfile.model_validate(data)
        if profile.customer_id in profiles:
            raise RuntimeError(f"Duplicate customer_id {profile.customer_id!r} in {path.name}")
        profiles[profile.customer_id] = profile
    if not profiles:
        raise RuntimeError(f"No customer profiles found in {CUSTOMERS_DIR}")
    return profiles


def get_customer_profiles() -> dict[str, CustomerProfile]:
    global _profiles
    if _profiles is None:
        _profiles = _load_profiles()
    return _profiles


def known_customer_ids() -> frozenset[str]:
    return frozenset(get_customer_profiles())


def validate_customer_id(customer_id: str) -> str:
    profiles = get_customer_profiles()
    if customer_id not in profiles:
        known = ", ".join(sorted(profiles))
        raise ValueError(f"Unknown customer_id {customer_id!r}; known: {known}")
    return customer_id


def get_customer_profile(customer_id: str) -> CustomerProfile:
    return get_customer_profiles()[validate_customer_id(customer_id)]
