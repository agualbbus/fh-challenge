"""SOP section extraction."""

from __future__ import annotations

from app.worker.sops import get_sop_section


def test_known_section_returns_content() -> None:
    section = get_sop_section("delivery_eta_checkpoint", "load_information_question")
    assert section
    assert "## " not in section  # only the section body, not the next header


def test_unknown_task_returns_empty() -> None:
    assert get_sop_section("nonexistent_task", "load_information_question") == ""


def test_unknown_section_returns_empty() -> None:
    assert get_sop_section("delivery_eta_checkpoint", "totally_made_up") == ""


def test_broker_messages_section_loads() -> None:
    section = get_sop_section("delivery_eta_checkpoint", "broker_messages")
    assert section
