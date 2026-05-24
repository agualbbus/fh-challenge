"""Pure helpers for load-state initialization and delta merging."""

from __future__ import annotations

from typing import Any


def init_load_state(load_id: str, seed: dict[str, Any]) -> dict[str, Any]:
    return {
        "load_id": load_id,
        "customer_id": seed.get("customer_id"),
        "milestone": seed.get("milestone", "on_route_to_delivery"),
        "load_data": seed.get("load_data", {}),
        "active_task": seed.get("active_task"),
    }


def merge_load_data(existing: dict[str, Any], delta: dict[str, Any]) -> dict[str, Any]:
    """Top-level merge; `load_data` is merged one level deep."""
    merged = {**existing}
    for key, value in delta.items():
        if key == "load_data" and isinstance(value, dict):
            merged["load_data"] = {**merged.get("load_data", {}), **value}
        else:
            merged[key] = value
    return merged
