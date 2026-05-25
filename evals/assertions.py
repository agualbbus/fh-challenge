"""Eval assertions against workflow query state."""

from __future__ import annotations

from typing import Any


def _tool_args_match(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    for key, value in expected.items():
        if actual.get(key) != value:
            return False
    return True


def assert_tool_called(
    tool_calls: list[dict[str, Any]],
    *,
    tool: str,
    contains: str | None = None,
    arguments: dict[str, Any] | None = None,
) -> None:
    matches = [tc for tc in tool_calls if tc.get("tool") == tool]
    if not matches:
        raise AssertionError(f"Required tool not called: {tool}")

    if contains is not None:
        # Case-insensitive so SOP-driven wording ("Checking on...") still matches
        # fixture substrings like "checking".
        haystack = str(matches).lower()
        if contains.lower() not in haystack:
            raise AssertionError(f"Tool {tool} calls did not contain {contains!r}: {matches}")

    if arguments is not None:
        if not any(_tool_args_match(tc.get("arguments", {}), arguments) for tc in matches):
            raise AssertionError(f"Tool {tool} missing arguments {arguments}: {matches}")


def assert_tool_forbidden(tool_calls: list[dict[str, Any]], tool: str) -> None:
    if any(tc.get("tool") == tool for tc in tool_calls):
        matches = [tc for tc in tool_calls if tc.get("tool") == tool]
        raise AssertionError(f"Forbidden tool called: {tool} -> {matches}")


def assert_state(milestone: str | None, expected_state: str) -> None:
    if milestone != expected_state:
        raise AssertionError(f"Expected milestone {expected_state!r}, got {milestone!r}")


def run_case_assertions(
    workflow_state: dict[str, Any],
    expected: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    tool_calls = workflow_state.get("tool_calls", [])
    milestone = workflow_state.get("milestone") or workflow_state.get("load_state", {}).get(
        "milestone"
    )

    for req in expected.get("required_tool_calls", []):
        try:
            assert_tool_called(
                tool_calls,
                tool=req["tool"],
                contains=req.get("contains"),
                arguments=req.get("arguments"),
            )
        except AssertionError as exc:
            errors.append(str(exc))

    for forbidden in expected.get("forbidden_tool_calls", []):
        try:
            assert_tool_forbidden(tool_calls, forbidden)
        except AssertionError as exc:
            errors.append(str(exc))

    if expected.get("expected_state"):
        try:
            assert_state(milestone, expected["expected_state"])
        except AssertionError as exc:
            errors.append(str(exc))

    return errors
