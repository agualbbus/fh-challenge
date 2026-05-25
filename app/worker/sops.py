"""SOP section loader for branch-scoped prompts."""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import BaseTool

from app.tools.tools import TOOLS_BY_NAME

SOPS_DIR = Path(__file__).resolve().parent.parent / "sops"

_SOP_FILES = {
    "delivery_eta_checkpoint": "on_route_to_delivery_eta_checkpoint.md",
    "confirm_delivery": "confirm_delivery.md",
}

_MILESTONE_TO_TASK = {
    "on_route_to_delivery": "delivery_eta_checkpoint",
    "at_delivery": "confirm_delivery",
    "delivered": "confirm_delivery",
    "pod_collected": "confirm_delivery",
}


# Per-SOP tool surface. Narrows the agent's choice to tools the SOP actually
# permits, instead of binding every tool on every turn. Tools shared by both
# SOPs are listed in both sets; tools unique to one SOP (e.g. update_eta vs
# check_attachment) only appear there. `send_email` is excluded — no SOP path
# uses it, and the eval fixtures forbid it.
_SOP_TOOL_NAMES: dict[str, tuple[str, ...]] = {
    "delivery_eta_checkpoint": (
        "send_sms",
        "send_slack_message",
        "update_eta",
        "validate_eta",
        "create_timer",
        "cancel_timers",
        "update_load_state",
        "get_load_info",
        "get_appointment_time",
        "create_issue",
        "create_task",
    ),
    "confirm_delivery": (
        "send_sms",
        "send_slack_message",
        "check_attachment",
        "forward_email",
        "update_load_state",
        "create_timer",
        "cancel_timer",
        "cancel_timers",
        "create_task",
        "create_issue",
        "get_load_info",
    ),
}


def task_for_milestone(milestone: str | None) -> str:
    """Deterministic mapping from load milestone to active SOP task.

    Used at seed time so SOP selection is a function of the seed's
    `initial_state` rather than a silent default in the agent prompt.
    """
    return _MILESTONE_TO_TASK.get(milestone or "", "delivery_eta_checkpoint")


def tools_for_sop(task_type: str | None) -> list[BaseTool]:
    """Return the tool subset the active SOP is allowed to call.

    Falls back to the ETA SOP set when the task is unknown, mirroring the
    default used by `task_for_milestone`.
    """
    names = _SOP_TOOL_NAMES.get(task_type or "") or _SOP_TOOL_NAMES["delivery_eta_checkpoint"]
    return [TOOLS_BY_NAME[name] for name in names]


def get_sop_document(task_type: str) -> str:
    """Return the full SOP markdown for the active task, or empty string if unknown."""
    filename = _SOP_FILES.get(task_type)
    if not filename:
        return ""
    path = SOPS_DIR / filename
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


