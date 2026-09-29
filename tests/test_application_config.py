"""The application loads one explicit literal configuration before construction."""

import pytest

from blooglyblob.config import AIConfigError, load_ai_config, load_runtime_environment
from scripts.deploy_config import read_env, serialize_env


def test_explicit_literal_file_and_process_precedence(tmp_path):
    values = {
        "OPENAI_API_KEY": "${SECRET}$(literal)",
        "RING_TOKEN": '{"quote":"x\\y"}',
        "FUTURE": 'line\none "two" \\ three $four',
    }
    path = tmp_path / "app.env"
    path.write_text(serialize_env(values))
    env = {"BLOOGLYBLOB_ENV_FILE": str(path), "OPENAI_API_KEY": "process-key"}
    load_runtime_environment(env)
    assert env["OPENAI_API_KEY"] == "process-key"
    assert env["RING_TOKEN"] == values["RING_TOKEN"]
    assert env["FUTURE"] == values["FUTURE"]
    assert read_env(path) == values
    assert env["BLOOGLYBLOB_STATE_DIR"] == "/var/lib/blooglyblob/brain"
    assert "SERVO_CALIBRATION_FILE" not in env
    assert "process-key" not in repr(load_ai_config(env))


def test_no_implicit_dotenv(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=unintended\n")
    env = {}
    load_runtime_environment(env)
    assert "OPENAI_API_KEY" not in env


@pytest.mark.parametrize("contents", ['OPENAI_API_KEY="secret', "bad secret line"])
def test_invalid_file_content_is_private(tmp_path, contents):
    path = tmp_path / "app.env"
    path.write_text(contents)
    with pytest.raises(AIConfigError) as error:
        load_runtime_environment({"BLOOGLYBLOB_ENV_FILE": str(path)})
    assert "secret" not in str(error.value)


def test_missing_explicit_file(tmp_path):
    with pytest.raises(AIConfigError, match="BLOOGLYBLOB_ENV_FILE"):
        load_runtime_environment({"BLOOGLYBLOB_ENV_FILE": str(tmp_path / "missing")})


@pytest.mark.parametrize(
    "key,value",
    [
        ("OPENAI_API_KEY", ""),
        ("MIC_GAIN", "secret"),
        ("OPENAI_INACTIVITY_SECONDS", "NaN"),
        ("OPENAI_SESSION_MAX_SECONDS", "invalid"),
    ],
)
def test_invalid_settings_are_private(key, value):
    with pytest.raises(AIConfigError) as error:
        load_ai_config({"OPENAI_API_KEY": "valid", key: value})
    assert key in str(error.value)
    assert "secret" not in str(error.value)


@pytest.mark.parametrize(
    "value",
    [
        "ends in slash\\",
        '\\"quoted"',
        "single 'quote'",
        "${VALUE}$(literal)",
        " spaces # literal ",
        "one\ntwo\r\nthree\tend",
        "café 日本語",
    ],
)
def test_literal_serialization_matches_runtime(tmp_path, value):
    path = tmp_path / "app.env"
    path.write_text(serialize_env({"FUTURE": value}))
    env = {"BLOOGLYBLOB_ENV_FILE": str(path)}
    load_runtime_environment(env)
    assert env["FUTURE"] == read_env(path)["FUTURE"] == value


def test_diagnostic_configuration_does_not_require_cloud_credentials():
    assert load_ai_config({}, require_credentials=False).openai_api_key is None
