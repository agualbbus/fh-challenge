"""Tests for the eval environment selector."""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from evals.env_config import EnvConfig, load_env_config, select_env

YAML_BODY = """\
default_env: local
environments:
  local:
    api_base_url: http://localhost:8000
    repetitions: 1
    poll_timeout_seconds: 30
  prod:
    api_base_url: https://prod.example.com/
    api_key_env: WT_KEY
    repetitions: 4
    poll_timeout_seconds: 120
"""


def _write(tmp_path: Path) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(YAML_BODY, encoding="utf-8")
    return p


def test_load_env_config_parses(tmp_path):
    cfg = load_env_config(_write(tmp_path))
    assert "local" in cfg["environments"]
    assert cfg["default_env"] == "local"


def test_load_env_config_rejects_missing_environments(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("default_env: local\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_env_config(p)


def test_select_env_cli_skip_prompt(tmp_path):
    cfg = load_env_config(_write(tmp_path))
    env = select_env(cfg, cli_env="local")
    assert isinstance(env, EnvConfig)
    assert env.name == "local"
    assert env.api_base_url == "http://localhost:8000"
    assert env.api_key is None
    assert env.repetitions == 1


def test_select_env_cli_unknown(tmp_path):
    cfg = load_env_config(_write(tmp_path))
    with pytest.raises(ValueError):
        select_env(cfg, cli_env="staging")


def test_select_env_strips_trailing_slash(tmp_path):
    cfg = load_env_config(_write(tmp_path))
    env = select_env(cfg, cli_env="prod")
    assert env.api_base_url == "https://prod.example.com"


def test_select_env_api_key_env(tmp_path, monkeypatch):
    monkeypatch.setenv("WT_KEY", "secret-123")
    cfg = load_env_config(_write(tmp_path))
    env = select_env(cfg, cli_env="prod")
    assert env.api_key == "secret-123"


def test_select_env_api_key_env_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("WT_KEY", raising=False)
    cfg = load_env_config(_write(tmp_path))
    env = select_env(cfg, cli_env="prod")
    assert env.api_key is None


def test_select_env_prompts_with_default(tmp_path):
    cfg = load_env_config(_write(tmp_path))
    stream = io.StringIO()
    # Empty input → default (local).
    env = select_env(cfg, cli_env=None, input_fn=lambda _prompt: "", stream=stream)
    assert env.name == "local"
    assert "local" in stream.getvalue()


def test_select_env_prompts_explicit_choice(tmp_path):
    cfg = load_env_config(_write(tmp_path))
    env = select_env(cfg, cli_env=None, input_fn=lambda _prompt: "prod", stream=io.StringIO())
    assert env.name == "prod"


def test_env_file_is_loaded(tmp_path, monkeypatch):
    """`evals/.env` populates os.environ at import — point dotenv at a temp file."""
    from dotenv import load_dotenv

    env_file = tmp_path / ".env"
    env_file.write_text("FH_EVAL_TEST_VAR=from-dotenv\n", encoding="utf-8")
    monkeypatch.delenv("FH_EVAL_TEST_VAR", raising=False)
    load_dotenv(env_file, override=False)
    assert os.environ.get("FH_EVAL_TEST_VAR") == "from-dotenv"


def test_select_env_reprompts_on_bad_choice(tmp_path):
    cfg = load_env_config(_write(tmp_path))
    answers = iter(["nope", "prod"])
    env = select_env(
        cfg,
        cli_env=None,
        input_fn=lambda _prompt: next(answers),
        stream=io.StringIO(),
    )
    assert env.name == "prod"
