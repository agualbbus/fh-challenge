"""Load data field helpers."""

from __future__ import annotations

from typing import Any


def get_delivery_stop(load_data: dict[str, Any]) -> dict[str, Any] | None:
    for stop in load_data.get("stops", []):
        if stop.get("type") == "delivery":
            return stop
    return None


def format_address(address: dict[str, Any]) -> str:
    parts = [address.get("line_1", "")]
    if address.get("line_2"):
        parts.append(address["line_2"])
    parts.append(
        f"{address.get('city', '')}, {address.get('state', '')} {address.get('postal_code', '')}"
    )
    return ", ".join(p for p in parts if p)


def get_load_field(load_data: dict[str, Any], field: str) -> str | None:
    delivery = get_delivery_stop(load_data)
    if delivery is None:
        return None

    if field == "delivery_address":
        return format_address(delivery.get("address", {}))
    if field == "receiver_phone":
        return delivery.get("reference_numbers", {}).get("receiver_phone")
    if field == "delivery_reference":
        return delivery.get("reference_numbers", {}).get("delivery")
    if field == "pickup_reference":
        for stop in load_data.get("stops", []):
            if stop.get("type") == "pickup":
                return stop.get("reference_numbers", {}).get("pickup")
        return None
    if field == "driver_contact":
        driver = load_data.get("contacts", {}).get("driver", {})
        phone = driver.get("phone")
        if phone:
            return phone
        name = " ".join(
            p for p in [driver.get("first_name"), driver.get("last_name")] if p
        )
        return name or None
    if field == "delivery_appointment":
        appt = delivery.get("appointment", {})
        start = appt.get("start_utc")
        tz = appt.get("timezone", "")
        if start:
            return f"{start} ({tz})"
        return None
    return None


def detect_requested_field(content: str) -> str:
    text = content.lower()
    if "address" in text:
        return "delivery_address"
    if "phone" in text or "receiver" in text:
        return "receiver_phone"
    if "reference" in text or "delivery number" in text:
        return "delivery_reference"
    if "pickup" in text and "number" in text:
        return "pickup_reference"
    if "appointment" in text or "appt" in text:
        return "delivery_appointment"
    return "delivery_address"
