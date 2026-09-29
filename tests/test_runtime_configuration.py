"""Entrypoint validates and loads the selected runtime before consumers."""

from unittest.mock import Mock
import os
import pytest
from blooglyblob import __main__ as entry
from blooglyblob import application


@pytest.fixture(autouse=True)
def isolated_entrypoint_environment(monkeypatch):
    # Entrypoint loading intentionally inserts defaults into its environment.
    # A private mapping contains every insertion, including keys not named by
    # individual tests' setenv/delenv calls.
    monkeypatch.setattr(os, "environ", {})


def test_constructs_one_application_without_mode_setting(monkeypatch):
    monkeypatch.delenv("AI_MODE", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("BLOOGLYBLOB_ENV_FILE", raising=False)
    selected, run = Mock(), Mock()
    monkeypatch.setattr(application, "Application", selected)
    monkeypatch.setattr(entry, "run_application", run)
    entry.main()
    assert selected.call_args.kwargs["config"].openai_api_key == "test-key"
    run.assert_called_once()


def test_missing_key_fails_before_application_construction(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("BLOOGLYBLOB_ENV_FILE", raising=False)
    selected = Mock()
    monkeypatch.setattr(application, "Application", selected)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        entry.main()
    selected.assert_not_called()
