"""Shared fixtures for unit tests."""

from __future__ import annotations

import os

# Disable LangSmith / LangChain tracing during tests. Set before any langchain
# imports so the client never starts a background tracer or contacts the API.
for _var in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING"):
    os.environ[_var] = "false"
for _var in ("LANGSMITH_API_KEY", "LANGCHAIN_API_KEY"):
    os.environ.pop(_var, None)

import pytest  # noqa: E402


@pytest.fixture
def base_load_data() -> dict:
    """Standard two-stop load_data payload used across router/agent tests."""
    return {
        "external_load_id": "FH-2026-001",
        "companies": {
            "broker": {"name": "Example Broker"},
            "shipper": {"name": "Example Shipper"},
            "carrier": {"name": "Example Carrier"},
        },
        "contacts": {},
        "stops": [
            {
                "stop_id": "pickup-1",
                "type": "pickup",
                "address": {
                    "line_1": "123 Pickup Ave",
                    "city": "Chicago",
                    "state": "IL",
                    "postal_code": "60601",
                    "country": "US",
                },
                "appointment": {"type": "fixed", "timezone": "America/Chicago"},
                "coordinates": {"lat": 41.0, "lng": -87.0},
                "reference_numbers": {},
            },
            {
                "stop_id": "delivery-1",
                "type": "delivery",
                "address": {
                    "line_1": "456 Delivery St",
                    "line_2": "Dock 4",
                    "city": "Dallas",
                    "state": "TX",
                    "postal_code": "75201",
                    "country": "US",
                },
                "appointment": {"type": "fixed", "timezone": "America/Chicago"},
                "coordinates": {"lat": 32.0, "lng": -96.0},
                "reference_numbers": {"receiver_phone": "+15555550200"},
            },
        ],
    }


@pytest.fixture
def base_load_state(base_load_data: dict) -> dict:
    return {
        "load_id": "load-test",
        "customer_id": "customer_a",
        "milestone": "on_route_to_delivery",
        "load_data": base_load_data,
        "active_task": "delivery_eta_checkpoint",
    }
