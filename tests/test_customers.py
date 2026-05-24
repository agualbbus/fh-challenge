"""Customer profile loader."""

from __future__ import annotations

import pytest

from app.customers.base import (
    get_customer_profile,
    get_customer_profiles,
    known_customer_ids,
    validate_customer_id,
)


def test_known_customer_ids_includes_seed_profiles() -> None:
    ids = known_customer_ids()
    assert {"customer_a", "customer_b", "customer_c"} <= ids


def test_get_customer_profiles_cached() -> None:
    assert get_customer_profiles() is get_customer_profiles()


def test_validate_customer_id_round_trips() -> None:
    assert validate_customer_id("customer_a") == "customer_a"


def test_validate_customer_id_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown customer_id"):
        validate_customer_id("not-a-customer")


def test_get_customer_profile_has_required_fields() -> None:
    profile = get_customer_profile("customer_b")
    assert profile.customer_id == "customer_b"
    assert profile.missing_load_info.slack_audience in {"internal", "broker", "customer"}
    assert profile.eta_followup_minutes > 0
