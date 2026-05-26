"""Eval environment selection.

The harness reads `evals/config.yaml` and resolves which environment to run
against. The CLI `--env <name>` skips the interactive prompt.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

_EVALS_DIR = Path(__file__).resolve().parent
CONFIG_PATH = _EVALS_DIR / "config.yaml"
ENV_FILE = _EVALS_DIR / ".env"

# Load evals/.env eagerly so `api_key_env` references resolve at select_env
# time. `override=False` keeps shell-exported values winning over the file.
load_dotenv(ENV_FILE, override=False)


@dataclass(frozen=True)
class EnvConfig:
    name: str
    api_base_url: str
    api_key: str | None
    repetitions: int
    poll_timeout_seconds: float


def load_env_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "environments" not in data:
        raise ValueError(f"Eval config at {path} missing top-level 'environments' key")
    return data


def _resolve_api_key(entry: dict[str, Any]) -> str | None:
    if entry.get("api_key"):
        return str(entry["api_key"])
    env_var = entry.get("api_key_env")
    if env_var:
        val = os.getenv(env_var, "").strip()
        return val or None
    return None


def _build(name: str, entry: dict[str, Any]) -> EnvConfig:
    if "api_base_url" not in entry:
        raise ValueError(f"Env '{name}' missing required 'api_base_url'")
    return EnvConfig(
        name=name,
        api_base_url=str(entry["api_base_url"]).rstrip("/"),
        api_key=_resolve_api_key(entry),
        repetitions=int(entry.get("repetitions", 1)),
        poll_timeout_seconds=float(entry.get("poll_timeout_seconds", 90)),
    )


def select_env(
    config: dict[str, Any],
    cli_env: str | None = None,
    *,
    input_fn=input,
    stream=sys.stderr,
) -> EnvConfig:
    environments = config["environments"]
    names = list(environments.keys())
    if not names:
        raise ValueError("No environments defined in eval config")

    if cli_env is not None:
        if cli_env not in environments:
            raise ValueError(f"Unknown env '{cli_env}'. Available: {', '.join(names)}")
        return _build(cli_env, environments[cli_env])

    default = config.get("default_env") or names[0]
    if default not in environments:
        default = names[0]

    print("Available eval environments:", file=stream)
    for n in names:
        marker = " (default)" if n == default else ""
        print(f"  - {n}{marker}", file=stream)

    while True:
        raw = input_fn(f"Select environment [{default}]: ").strip()
        choice = raw or default
        if choice in environments:
            return _build(choice, environments[choice])
        print(
            f"  unknown env '{choice}'; choose one of: {', '.join(names)}",
            file=stream,
        )
