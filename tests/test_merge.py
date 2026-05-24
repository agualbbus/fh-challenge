"""Pure helpers in app/worker/merge.py."""

from __future__ import annotations

from app.worker.merge import init_load_state, merge_load_data


def test_init_load_state_defaults() -> None:
    state = init_load_state("load-1", {"customer_id": "customer_a"})
    assert state == {
        "load_id": "load-1",
        "customer_id": "customer_a",
        "milestone": "on_route_to_delivery",
        "load_data": {},
        "active_task": None,
    }


def test_init_load_state_passes_through_overrides() -> None:
    seed = {
        "customer_id": "customer_b",
        "milestone": "at_delivery",
        "load_data": {"external_load_id": "FH-9"},
        "active_task": "confirm_delivery",
    }
    state = init_load_state("load-9", seed)
    assert state["milestone"] == "at_delivery"
    assert state["active_task"] == "confirm_delivery"
    assert state["load_data"]["external_load_id"] == "FH-9"


def test_merge_load_data_overrides_top_level_keys() -> None:
    existing = {"milestone": "on_route_to_delivery", "load_data": {"a": 1}}
    merged = merge_load_data(existing, {"milestone": "at_delivery"})
    assert merged["milestone"] == "at_delivery"
    assert merged["load_data"] == {"a": 1}


def test_merge_load_data_deep_merges_load_data_one_level() -> None:
    existing = {"load_data": {"a": 1, "b": 2}}
    merged = merge_load_data(existing, {"load_data": {"b": 99, "c": 3}})
    assert merged["load_data"] == {"a": 1, "b": 99, "c": 3}


def test_merge_load_data_does_not_mutate_inputs() -> None:
    existing = {"load_data": {"a": 1}}
    delta = {"load_data": {"b": 2}}
    merge_load_data(existing, delta)
    assert existing == {"load_data": {"a": 1}}
    assert delta == {"load_data": {"b": 2}}
