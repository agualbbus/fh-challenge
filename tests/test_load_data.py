"""Pure helpers in app/worker/load_data.py."""

from __future__ import annotations

from app.worker.load_data import (
    detect_requested_field,
    format_address,
    get_delivery_stop,
    get_load_field,
)


def _delivery_stop(**overrides):
    stop = {
        "type": "delivery",
        "address": {
            "line_1": "456 Delivery St",
            "line_2": "Dock 4",
            "city": "Dallas",
            "state": "TX",
            "postal_code": "75201",
        },
        "appointment": {"start_utc": "2026-05-11T18:00:00Z", "timezone": "America/Chicago"},
        "reference_numbers": {
            "delivery": "DEL-1",
            "receiver_phone": "+15555550200",
        },
    }
    stop.update(overrides)
    return stop


def test_format_address_skips_empty_line_2():
    assert format_address({"line_1": "1 Main", "city": "X", "state": "Y", "postal_code": "Z"}) == (
        "1 Main, X, Y Z"
    )


def test_format_address_includes_line_2():
    addr = {"line_1": "1 Main", "line_2": "Apt 2", "city": "X", "state": "Y", "postal_code": "Z"}
    assert "Apt 2" in format_address(addr)


def test_get_delivery_stop_none_when_missing():
    assert get_delivery_stop({"stops": [{"type": "pickup"}]}) is None


def test_get_load_field_resolvers():
    delivery = _delivery_stop()
    load = {
        "stops": [
            {
                "type": "pickup",
                "reference_numbers": {"pickup": "PU-1"},
            },
            delivery,
        ],
        "contacts": {"driver": {"phone": "+15555550100", "first_name": "Ana"}},
    }
    assert "456 Delivery St" in get_load_field(load, "delivery_address")
    assert get_load_field(load, "receiver_phone") == "+15555550200"
    assert get_load_field(load, "delivery_reference") == "DEL-1"
    assert get_load_field(load, "pickup_reference") == "PU-1"
    assert get_load_field(load, "driver_contact") == "+15555550100"
    assert "2026-05-11" in get_load_field(load, "delivery_appointment")
    assert get_load_field(load, "unknown") is None


def test_get_load_field_no_delivery_returns_none():
    assert get_load_field({"stops": []}, "delivery_address") is None


def test_get_load_field_driver_contact_falls_back_to_name():
    load = {
        "stops": [_delivery_stop()],
        "contacts": {"driver": {"first_name": "Ana", "last_name": "K"}},
    }
    assert get_load_field(load, "driver_contact") == "Ana K"


def test_get_load_field_driver_contact_missing():
    load = {"stops": [_delivery_stop()], "contacts": {"driver": {}}}
    assert get_load_field(load, "driver_contact") is None


def test_get_load_field_appointment_missing_start():
    stop = _delivery_stop(appointment={"timezone": "X"})
    assert get_load_field({"stops": [stop]}, "delivery_appointment") is None


def test_detect_requested_field_branches():
    assert detect_requested_field("What is the delivery ADDRESS?") == "delivery_address"
    assert detect_requested_field("receiver phone please") == "receiver_phone"
    assert detect_requested_field("delivery number?") == "delivery_reference"
    assert detect_requested_field("pickup number?") == "pickup_reference"
    assert detect_requested_field("what time is the appointment?") == "delivery_appointment"
    assert detect_requested_field("unrelated chatter") == "delivery_address"
