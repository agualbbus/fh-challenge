"""Fixture-driven eval harness — HTTP ingress + LangGraph checkpoint state."""

from __future__ import annotations

import asyncio
import copy
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from evals.assertions import CaseResult, evaluate_case

FIXTURES_PATH = Path(__file__).resolve().parent / "fixtures" / "test-cases.json"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"

MOCK_CASES = {
    "3b_load_question_found",
    "3c_load_question_missing",
    "3d_truck_broken",
    "3f_driver_provides_eta",
    "3h_fresh_tracking_three_pings_in_geofence",
    "3i_not_tracking_driver_says_arrived",
    "3j_not_tracking_driver_sends_pod",
    "3k_broker_email_ignore",
}


def _parse_path(path: str) -> list[str | int]:
    parts: list[str | int] = []
    current = ""
    i = 0
    while i < len(path):
        ch = path[i]
        if ch == ".":
            if current:
                parts.append(current)
                current = ""
            i += 1
        elif ch == "[":
            if current:
                parts.append(current)
                current = ""
            j = path.index("]", i)
            parts.append(int(path[i + 1 : j]))
            i = j + 1
        else:
            current += ch
            i += 1
    if current:
        parts.append(current)
    return parts


def _apply_patch(obj: Any, path: str, value: Any) -> None:
    parts = _parse_path(path)
    target = obj
    for part in parts[:-1]:
        target = target[part]
    leaf = parts[-1]
    # Null at a leaf means "absent" (matches the canonical schema which forbids
    # null values for string fields); pop rather than set None.
    if value is None and isinstance(target, dict) and isinstance(leaf, str):
        target.pop(leaf, None)
    else:
        target[leaf] = value


def _build_load_seed(
    case: dict[str, Any], base_load: dict[str, Any], run_id: str
) -> dict[str, Any]:
    load_data = copy.deepcopy(base_load["load_data"])
    for path, value in (case.get("load_data_patch") or {}).items():
        _apply_patch(load_data, path, value)

    return {
        "load_id": f"eval-{case['id']}-{run_id}",
        "customer_id": case.get("customer_id", base_load["customer_id"]),
        "initial_state": case.get("initial_state", base_load["initial_state"]),
        "load_data": load_data,
    }


async def _query_load_state(load_id: str) -> dict[str, Any]:
    from app.config import get_settings
    from app.worker.checkpointer import init_checkpointer
    from app.worker.graph import query_load_state

    settings = get_settings()
    cp = await init_checkpointer(settings.database_url)
    return await query_load_state(cp, load_id)


async def _wait_for_tools(
    load_id: str, min_count: int, timeout_seconds: float = 30.0
) -> dict[str, Any]:
    last: dict[str, Any] = {}
    try:
        async with asyncio.timeout(timeout_seconds):
            while True:
                last = await _query_load_state(load_id)
                milestone = last.get("milestone") or last.get("load_state", {}).get("milestone")
                if milestone and len(last.get("tool_calls", [])) >= min_count:
                    return last
                await asyncio.sleep(0.5)
    except TimeoutError:
        return last


async def run_case(
    client: httpx.AsyncClient,
    case: dict[str, Any],
    base_load: dict[str, Any],
    run_id: str,
) -> tuple[bool, list[str], dict[str, Any], CaseResult]:
    seed = _build_load_seed(case, base_load, run_id)
    load_id = seed["load_id"]
    errors: list[str] = []

    resp = await client.post("/loads", json=seed)
    if resp.status_code not in (202, 409):
        return (
            False,
            [f"POST /loads failed: {resp.status_code} {resp.text}"],
            {"tool_calls": [], "milestone": None},
            CaseResult(errors=[f"POST /loads failed: {resp.status_code}"]),
        )

    for event in case.get("events", []):
        event_payload = copy.deepcopy(event)
        event_payload["load_id"] = load_id
        event_payload["customer_id"] = seed["customer_id"]
        # Suffix event_id with run_id so SQS FIFO dedup (5-min window) does not
        # swallow repeat eval runs that reuse fixture event_ids.
        if event_payload.get("event_id"):
            event_payload["event_id"] = f"{event_payload['event_id']}-{run_id}"
        path = {
            "inbound_communication": "/events/inbound-communication",
            "tracking": "/events/tracking",
            "load_update": "/events/load-update",
        }.get(event_payload["event_type"])
        if not path:
            errors.append(f"Unknown event_type: {event_payload['event_type']}")
            continue
        resp = await client.post(path, json=event_payload)
        if resp.status_code != 202:
            errors.append(f"POST {path} failed: {resp.status_code} {resp.text}")

    expected = case.get("expected", {})
    min_tools = len(expected.get("required_tool_calls", []))
    state = await _wait_for_tools(load_id, min_tools)
    case_result = evaluate_case(state, expected)
    errors.extend(case_result.errors)
    return len(errors) == 0, errors, state, case_result


async def run_all(api_base: str, case_filter: set[str] | None = None) -> int:
    data = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    base_load = data["base_load"]
    cases = data["cases"]
    if case_filter:
        cases = [c for c in cases if c["id"] in case_filter]

    # Per-run suffix isolates this harness invocation from prior runs:
    # avoids LangGraph checkpoint accumulation and SQS FIFO dedup hits.
    run_id = uuid.uuid4().hex[:8]
    print(f"Eval run_id: {run_id}", file=sys.stderr)

    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(base_url=api_base, timeout=30.0) as client:
        health = await client.get("/health")
        if health.status_code != 200:
            print(f"API health check failed: {health.status_code}", file=sys.stderr)
            return 1

        for case in cases:
            ok, errors, state, case_result = await run_case(client, case, base_load, run_id)
            load_id = f"eval-{case['id']}-{run_id}"
            results.append(
                {
                    "case": case,
                    "ok": ok,
                    "errors": errors,
                    "state": state,
                    "result": case_result,
                    "load_id": load_id,
                    "thread_id": f"load-{load_id}",
                }
            )
            status = "PASS" if ok else "FAIL"
            print(f"{status} {case['id']}")
            for err in errors:
                print(f"  - {err}")

    report_path = _write_report(results)
    print(f"Eval report written: {report_path}", file=sys.stderr)
    failed = sum(1 for r in results if not r["ok"])
    return 1 if failed else 0


def _score(case_result: CaseResult) -> tuple[int, int]:
    """Return (checks_passed, checks_total) for a case."""
    passed = sum(case_result.required_results) + sum(case_result.forbidden_results)
    total = len(case_result.required_results) + len(case_result.forbidden_results)
    if case_result.milestone_ok is not None:
        total += 1
        if case_result.milestone_ok:
            passed += 1
    return passed, total


def _pct(passed: int, total: int) -> str:
    if total == 0:
        return "—"
    return f"{passed / total * 100:.1f}%"


def _fmt_expected_tool(req: dict[str, Any]) -> str:
    parts = [f"`{req['tool']}`"]
    if req.get("contains") is not None:
        parts.append(f"contains={req['contains']!r}")
    if req.get("arguments"):
        parts.append(f"arguments={json.dumps(req['arguments'], sort_keys=True)}")
    return " — ".join(parts)


def _fmt_actual_tool(tc: dict[str, Any]) -> str:
    tool = tc.get("tool", "?")
    args = tc.get("arguments", {})
    rendered = json.dumps(args, sort_keys=True, default=str).replace("\n", "\\n")
    return f"`{tool}` — {rendered}"


def _write_report(results: list[dict[str, Any]]) -> Path:
    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    failed = total - passed

    overall_passed = 0
    overall_total = 0
    for r in results:
        cp, ct = _score(r["result"])
        overall_passed += cp
        overall_total += ct

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    report_path = REPORTS_DIR / f"{timestamp}_EVAL_REPORT.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "# Eval Report",
        "",
        f"_Generated: {timestamp}_",
        "",
        (
            f"**Summary:** {passed}/{total} passed, {failed} failed — "
            f"overall score {_pct(overall_passed, overall_total)} "
            f"({overall_passed}/{overall_total} checks)"
        ),
        "",
        "## Scoring",
        "",
        "Each case contributes `len(required) + len(forbidden) + (1 if expected_state else 0)` checks.",
        "A required check passes if the tool was called with the expected args/contents. "
        "A forbidden check passes if the tool was **not** called. "
        "The milestone check passes if the actual milestone matches `expected_state`. "
        "Extra tool calls that are neither required nor forbidden do **not** affect the score.",
        "",
        "## Results",
        "",
        "| Case | Result | Required (matched/total) | Forbidden called | Milestone | Score | Thread ID |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        case = r["case"]
        cr: CaseResult = r["result"]
        expected = case.get("expected", {})
        required = expected.get("required_tool_calls", []) or []
        forbidden = expected.get("forbidden_tool_calls", []) or []

        required_matched = sum(cr.required_results)
        forbidden_called = len(forbidden) - sum(cr.forbidden_results)
        if cr.milestone_ok is None:
            milestone_cell = "—"
        else:
            milestone_cell = "PASS" if cr.milestone_ok else "FAIL"
        cp, ct = _score(cr)

        required_cell = f"{required_matched}/{len(required)}" if required else "—"
        forbidden_cell = str(forbidden_called) if forbidden else "—"

        lines.append(
            f"| {case['id']} | {'PASS' if r['ok'] else 'FAIL'} "
            f"| {required_cell} | {forbidden_cell} | {milestone_cell} | {_pct(cp, ct)} "
            f"| `{r['thread_id']}` |"
        )

    lines += ["", "## Case details", ""]
    for r in results:
        case = r["case"]
        state = r["state"]
        cr = r["result"]
        expected = case.get("expected", {})
        tool_calls = state.get("tool_calls", []) or []
        required = expected.get("required_tool_calls", []) or []
        forbidden = expected.get("forbidden_tool_calls", []) or []
        expected_state = expected.get("expected_state")
        actual_milestone = state.get("milestone") or state.get("load_state", {}).get("milestone")
        cp, ct = _score(cr)

        lines.append(f"### {case['id']} — {'PASS' if r['ok'] else 'FAIL'} ({_pct(cp, ct)})")
        lines.append("")
        if case.get("title"):
            lines.append(f"_{case['title']}_")
            lines.append("")

        lines.append(f"- **Customer:** `{case.get('customer_id', '—')}`")
        lines.append(f"- **Initial state:** `{case.get('initial_state', '—')}`")
        lines.append(f"- **Thread ID (LangSmith):** `{r['thread_id']}`")
        lines.append(
            f"- **Expected milestone:** `{expected_state or '—'}`"
            f" — **actual:** `{actual_milestone or '—'}`"
        )
        lines.append(f"- **Score:** {cp}/{ct} checks ({_pct(cp, ct)})")
        lines.append("")

        lines.append("**Required tool calls:**")
        if required:
            for req, ok in zip(required, cr.required_results, strict=False):
                marker = "✓" if ok else "✗"
                lines.append(f"- {marker} {_fmt_expected_tool(req)}")
        else:
            lines.append("- _(none)_")
        lines.append("")

        if forbidden:
            lines.append("**Forbidden tool calls:**")
            for tool, ok in zip(forbidden, cr.forbidden_results, strict=False):
                marker = "✓" if ok else "✗ called"
                lines.append(f"- {marker} `{tool}`")
            lines.append("")

        lines.append("**Actual tool calls:**")
        if tool_calls:
            for tc in tool_calls:
                lines.append(f"- {_fmt_actual_tool(tc)}")
        else:
            lines.append("- _(none)_")
        lines.append("")

        if r["errors"]:
            lines.append("**Failures:**")
            for err in r["errors"]:
                lines.append(f"- {err}")
            lines.append("")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> int:
    from app.asyncio_compat import run as run_async
    from app.config import get_settings

    settings = get_settings()
    return run_async(run_all(settings.api_base_url, MOCK_CASES))


if __name__ == "__main__":
    raise SystemExit(main())
