"""Fixture-driven eval harness — HTTP ingress + LangGraph checkpoint state."""

from __future__ import annotations

import asyncio
import copy
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from evals.assertions import run_case_assertions

FIXTURES_PATH = Path(__file__).resolve().parent / "fixtures" / "test-cases.json"
REPORT_PATH = Path(__file__).resolve().parent / "EVAL_REPORT.md"

PHASE3_CASES = {"3b_load_question_found", "3c_load_question_missing"}


def _apply_patch(obj: Any, path: str, value: Any) -> None:
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
            continue
        if ch == "[":
            if current:
                parts.append(current)
                current = ""
            j = path.index("]", i)
            parts.append(int(path[i + 1 : j]))
            i = j + 1
            continue
        current += ch
        i += 1
    if current:
        parts.append(current)

    target = obj
    for part in parts[:-1]:
        target = target[part]
    target[parts[-1]] = value


def _build_load_seed(case: dict[str, Any], base_load: dict[str, Any]) -> dict[str, Any]:
    load_data = copy.deepcopy(base_load["load_data"])
    for path, value in (case.get("load_data_patch") or {}).items():
        _apply_patch(load_data, path, value)

    return {
        "load_id": f"eval-{case['id']}",
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


async def _wait_for_tools(load_id: str, min_count: int, timeout: float = 30.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = await _query_load_state(load_id)
        if len(last.get("tool_calls", [])) >= min_count:
            return last
        await asyncio.sleep(0.5)
    return last


async def run_case(
    client: httpx.AsyncClient,
    case: dict[str, Any],
    base_load: dict[str, Any],
) -> tuple[bool, list[str]]:
    seed = _build_load_seed(case, base_load)
    load_id = seed["load_id"]
    errors: list[str] = []

    resp = await client.post("/loads", json=seed)
    if resp.status_code not in (202, 409):
        return False, [f"POST /loads failed: {resp.status_code} {resp.text}"]

    for event in case.get("events", []):
        event_payload = copy.deepcopy(event)
        event_payload["load_id"] = load_id
        event_payload["customer_id"] = seed["customer_id"]
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
    errors.extend(run_case_assertions(state, expected))
    return len(errors) == 0, errors


async def run_all(api_base: str, case_filter: set[str] | None = None) -> int:
    data = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    base_load = data["base_load"]
    cases = data["cases"]
    if case_filter:
        cases = [c for c in cases if c["id"] in case_filter]

    results: list[tuple[str, bool, list[str]]] = []
    async with httpx.AsyncClient(base_url=api_base, timeout=30.0) as client:
        health = await client.get("/health")
        if health.status_code != 200:
            print(f"API health check failed: {health.status_code}", file=sys.stderr)
            return 1

        for case in cases:
            ok, errors = await run_case(client, case, base_load)
            results.append((case["id"], ok, errors))
            status = "PASS" if ok else "FAIL"
            print(f"{status} {case['id']}")
            for err in errors:
                print(f"  - {err}")

    _write_report(results)
    failed = sum(1 for _, ok, _ in results if not ok)
    return 1 if failed else 0


def _write_report(results: list[tuple[str, bool, list[str]]]) -> None:
    lines = ["# Eval Report", "", "| Case | Result | Notes |", "| --- | --- | --- |"]
    for case_id, ok, errors in results:
        notes = "; ".join(errors) if errors else "ok"
        lines.append(f"| {case_id} | {'PASS' if ok else 'FAIL'} | {notes} |")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    from app.asyncio_compat import run as run_async
    from app.config import get_settings

    settings = get_settings()
    return run_async(run_all(settings.api_base_url, PHASE3_CASES))


if __name__ == "__main__":
    raise SystemExit(main())
