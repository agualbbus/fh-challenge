"""SOP section loader for branch-scoped prompts."""

from __future__ import annotations

from pathlib import Path

SOPS_DIR = Path(__file__).resolve().parent.parent / "sops"

_SECTION_FILES = {
    "delivery_eta_checkpoint": "on_route_to_delivery_eta_checkpoint.md",
    "confirm_delivery": "confirm_delivery.md",
}

_SECTION_HEADERS = {
    "load_information_question": "Load Information Question",
    "operational_issue": "Operational Issue",
    "broker_messages": "Broker Messages",
    "driver_provides_eta": "Driver Provides ETA",
}


def get_sop_section(task_type: str, section_key: str) -> str:
    filename = _SECTION_FILES.get(task_type)
    if not filename:
        return ""
    path = SOPS_DIR / filename
    if not path.exists():
        return ""
    header = _SECTION_HEADERS.get(section_key, section_key.replace("_", " ").title())
    text = path.read_text(encoding="utf-8")
    marker = f"## {header}"
    if marker not in text:
        return ""
    start = text.index(marker) + len(marker)
    rest = text[start:].lstrip("\n")
    end = rest.find("\n## ")
    section = rest[:end] if end != -1 else rest
    return section.strip()
