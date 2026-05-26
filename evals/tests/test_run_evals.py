"""Unit tests for the eval harness — covers both single-run and parallel modes."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from evals import run_evals
from evals.assertions import CaseResult
from evals.env_config import EnvConfig
from evals.run_evals import (
    _aggregate_table,
    _apply_patch,
    _build_aggregated_report,
    _build_load_seed,
    _parse_cli,
    _parse_path,
    _pct,
    _score,
    build_report_body,
    run_all,
)


def _env(name: str = "test", repetitions: int = 1) -> EnvConfig:
    return EnvConfig(
        name=name,
        api_base_url="http://x",
        api_key=None,
        repetitions=repetitions,
        poll_timeout_seconds=5.0,
    )


def test_parse_path_dotted():
    assert _parse_path("a.b.c") == ["a", "b", "c"]


def test_parse_path_indexed():
    assert _parse_path("items[0].name") == ["items", 0, "name"]


def test_parse_path_trailing_index():
    assert _parse_path("tags[2]") == ["tags", 2]


def test_apply_patch_sets_nested():
    obj = {"a": {"b": 1}}
    _apply_patch(obj, "a.b", 99)
    assert obj == {"a": {"b": 99}}


def test_apply_patch_array_index():
    obj = {"items": [{"name": "x"}, {"name": "y"}]}
    _apply_patch(obj, "items[1].name", "z")
    assert obj["items"][1]["name"] == "z"


def test_apply_patch_null_pops_leaf():
    obj = {"a": {"b": "keep", "c": "drop"}}
    _apply_patch(obj, "a.c", None)
    assert obj == {"a": {"b": "keep"}}


def test_pct_zero_total():
    assert _pct(0, 0) == "—"


def test_pct_calculation():
    assert _pct(3, 4) == "75.0%"


def test_score_all_pass():
    cr = CaseResult(
        required_results=[True, True],
        forbidden_results=[True],
        milestone_ok=True,
    )
    assert _score(cr) == (4, 4)


def test_score_partial():
    cr = CaseResult(
        required_results=[True, False],
        forbidden_results=[True],
        milestone_ok=False,
    )
    assert _score(cr) == (2, 4)


def test_score_no_milestone():
    cr = CaseResult(required_results=[True], forbidden_results=[], milestone_ok=None)
    assert _score(cr) == (1, 1)


def test_build_load_seed_applies_patch_and_uses_case_customer():
    case = {
        "id": "demo",
        "customer_id": "cust-x",
        "initial_state": "in_transit",
        "load_data_patch": {"driver.name": "Alice"},
    }
    base = {
        "customer_id": "cust-default",
        "initial_state": "in_transit",
        "load_data": {"driver": {"name": "Bob"}, "load_id": "L1"},
    }
    seed = _build_load_seed(case, base, run_id="abc")
    assert seed["customer_id"] == "cust-x"
    assert seed["load_id"] == "eval-demo-abc"
    assert seed["load_data"]["driver"]["name"] == "Alice"
    assert base["load_data"]["driver"]["name"] == "Bob"


def test_build_load_seed_falls_back_to_base_customer():
    case = {"id": "demo"}
    base = {
        "customer_id": "cust-default",
        "initial_state": "scheduled",
        "load_data": {"x": 1},
    }
    seed = _build_load_seed(case, base, run_id="run1")
    assert seed["customer_id"] == "cust-default"
    assert seed["initial_state"] == "scheduled"


def _fake_result(case_id: str, ok: bool, run_id: str = "run") -> dict:
    cr = CaseResult(
        required_results=[ok],
        forbidden_results=[],
        milestone_ok=ok,
        errors=[] if ok else ["boom"],
    )
    return {
        "case": {"id": case_id, "title": case_id, "customer_id": "c", "initial_state": "s"},
        "ok": ok,
        "errors": [] if ok else ["boom"],
        "state": {"tool_calls": [], "milestone": "at_delivery" if ok else None},
        "result": cr,
        "load_id": f"eval-{case_id}-{run_id}",
        "thread_id": f"load-eval-{case_id}-{run_id}",
        "run_id": run_id,
    }


def test_build_report_body_with_header():
    results = [_fake_result("a", True), _fake_result("b", False)]
    lines = build_report_body(results, include_header=True, env=_env("local"))
    body = "\n".join(lines)
    assert body.startswith("# Eval Report")
    assert "1/2 passed" in body
    assert "## Results" in body
    assert "## Case details" in body
    assert "**Environment:** `local`" in body


def test_build_report_body_without_header():
    results = [_fake_result("a", True)]
    lines = build_report_body(results, include_header=False)
    body = "\n".join(lines)
    assert "# Eval Report" not in body
    assert "**Summary:**" in body


def test_parse_cli_defaults():
    args = _parse_cli([])
    assert args.repetitions is None
    assert args.env is None
    assert args.fixtures.name == "test-cases.json"


def test_parse_cli_overrides(tmp_path):
    f = tmp_path / "other.json"
    f.write_text("{}", encoding="utf-8")
    args = _parse_cli(["--env", "prod", "--repetitions", "3", "--fixtures", str(f)])
    assert args.env == "prod"
    assert args.repetitions == 3
    assert args.fixtures == f


def test_aggregate_table_per_case_pass_rate():
    run1 = [_fake_result("a", True, "r1"), _fake_result("b", False, "r1")]
    run2 = [_fake_result("a", True, "r2"), _fake_result("b", True, "r2")]
    run3 = [_fake_result("a", False, "r3"), _fake_result("b", True, "r3")]
    lines = _aggregate_table([run1, run2, run3])
    table = "\n".join(lines)
    assert "Run1" in table and "Run3" in table
    a_row = next(line for line in lines if line.startswith("| a |"))
    assert "PASS" in a_row and "FAIL" in a_row and "2/3" in a_row
    b_row = next(line for line in lines if line.startswith("| b |"))
    assert "2/3" in b_row


def test_aggregate_table_handles_missing_case():
    run1 = [_fake_result("a", True, "r1"), _fake_result("b", True, "r1")]
    run2 = [_fake_result("a", True, "r2")]
    lines = _aggregate_table([run1, run2])
    b_row = next(line for line in lines if line.startswith("| b |"))
    assert "—" in b_row
    assert "1/1" in b_row


def test_build_aggregated_report_structure(tmp_path):
    run1 = [_fake_result("a", True, "r1")]
    run2 = [_fake_result("a", False, "r2")]
    lines = _build_aggregated_report(
        [run1, run2],
        fixtures_path=tmp_path / "x.json",
        timestamp="2026-01-01T00-00-00Z",
        env=_env("local"),
    )
    body = "\n".join(lines)
    assert body.startswith("# Parallel Eval Report (N=2)")
    assert "## Aggregated Summary" in body
    assert "## Individual Runs" in body
    assert "### Run 1 (run_id=`r1`)" in body
    assert "### Run 2 (run_id=`r2`)" in body
    assert "1/2 suite-runs fully passed" in body
    assert "**Environment:** `local`" in body


@pytest.mark.asyncio
async def test_run_all_parallel_writes_aggregated_report(monkeypatch, tmp_path):
    monkeypatch.setattr(run_evals, "REPORTS_DIR", tmp_path)

    call_count = {"n": 0}

    async def fake_execute_suite(env, fixtures_path, case_filter, run_id):
        call_count["n"] += 1
        ok = call_count["n"] % 2 == 1
        return [_fake_result("demo", ok, run_id)]

    monkeypatch.setattr(run_evals, "execute_suite", fake_execute_suite)

    rc = await run_all(
        env=_env(),
        case_filter=None,
        fixtures_path=tmp_path / "f.json",
        repetitions=3,
    )
    assert rc == 1
    assert call_count["n"] == 3
    reports = list(tmp_path.glob("*_PARALLEL_EVAL_REPORT.md"))
    assert len(reports) == 1
    content = reports[0].read_text(encoding="utf-8")
    assert "# Parallel Eval Report (N=3)" in content
    assert content.count("### Run ") == 3


@pytest.mark.asyncio
async def test_run_all_single_writes_single_report(monkeypatch, tmp_path):
    monkeypatch.setattr(run_evals, "REPORTS_DIR", tmp_path)

    async def fake_execute_suite(env, fixtures_path, case_filter, run_id):
        return [_fake_result("demo", True, run_id)]

    monkeypatch.setattr(run_evals, "execute_suite", fake_execute_suite)

    rc = await run_all(
        env=_env(),
        case_filter=None,
        fixtures_path=tmp_path / "f.json",
        repetitions=1,
    )
    assert rc == 0
    single = list(tmp_path.glob("*_EVAL_REPORT.md"))
    parallel = list(tmp_path.glob("*_PARALLEL_EVAL_REPORT.md"))
    assert len(single) == 1
    assert len(parallel) == 0


@pytest.mark.asyncio
async def test_run_all_uses_env_repetitions_when_none(monkeypatch, tmp_path):
    monkeypatch.setattr(run_evals, "REPORTS_DIR", tmp_path)

    call_count = {"n": 0}

    async def fake_execute_suite(env, fixtures_path, case_filter, run_id):
        call_count["n"] += 1
        return [_fake_result("demo", True, run_id)]

    monkeypatch.setattr(run_evals, "execute_suite", fake_execute_suite)

    rc = await run_all(
        env=_env(repetitions=2),
        case_filter=None,
        fixtures_path=tmp_path / "f.json",
        repetitions=None,
    )
    assert rc == 0
    assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_run_all_zero_repetitions_rejected(tmp_path):
    rc = await run_all(
        env=_env(),
        case_filter=None,
        fixtures_path=tmp_path / "f.json",
        repetitions=0,
    )
    assert rc == 2
