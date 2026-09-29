"""Explicit application settings; safe to import before hardware or API clients."""

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
import math
import os
import sys
from pathlib import Path


class AIConfigError(ValueError):
    """Invalid application configuration (messages never include values)."""


@dataclass(frozen=True)
class AIConfig:
    openai_api_key: str | None = field(default=None, repr=False)


STATE_DEFAULTS = {
    "BLOOGLYBLOB_STATE_DIR": "/var/lib/blooglyblob/brain",
}


def load_runtime_environment(environ: MutableMapping[str, str] | None = None) -> None:
    """Called once by each entry point, before modules that consume settings.

    No cwd discovery, interpolation, or import-time mutation. Explicit process
    values win. The dotenv parser is used directly to reject malformed input
    without python-dotenv logging potentially sensitive source material.
    """
    from dotenv.parser import parse_stream

    env = os.environ if environ is None else environ
    selected = env.get("BLOOGLYBLOB_ENV_FILE")
    values: dict[str, str] = {}
    if selected is not None:
        path = Path(selected)
        if not selected or not path.is_file():
            raise AIConfigError("BLOOGLYBLOB_ENV_FILE must name an existing file")
        try:
            with path.open() as stream:
                for binding in parse_stream(stream):
                    if binding.error or (
                        binding.key is not None and binding.value is None
                    ):
                        raise AIConfigError(
                            "BLOOGLYBLOB_ENV_FILE contains an invalid assignment"
                        )
                    if binding.key is not None and binding.value is not None:
                        values[binding.key] = binding.value
        except (OSError, UnicodeError):
            raise AIConfigError("BLOOGLYBLOB_ENV_FILE could not be read") from None
    for key, value in (STATE_DEFAULTS | values).items():
        env.setdefault(key, value)


def validate_settings(env: Mapping[str, str]) -> None:
    """Check conversions before API/hardware construction; keep existing limits."""
    for key in ("MIC_GAIN", "OPENAI_INACTIVITY_SECONDS", "OPENAI_SESSION_MAX_SECONDS"):
        if key not in env:
            continue
        try:
            value = int(env[key]) if key == "MIC_GAIN" else float(env[key])
            if not math.isfinite(value) or (key != "MIC_GAIN" and value <= 0):
                raise ValueError
        except (ValueError, OverflowError):
            raise AIConfigError(
                f"{key} must be a finite number"
                if key == "MIC_GAIN"
                else f"{key} must be positive and finite"
            ) from None
    for key in (*STATE_DEFAULTS, "BLOOGLYBLOB_MEDIA_DIR"):
        if key in env and not env[key].strip():
            raise AIConfigError(f"{key} must name a path")


def load_ai_config(
    environ: Mapping[str, str] | None = None, *, require_credentials: bool = True
) -> AIConfig:
    env = os.environ if environ is None else environ
    if sys.version_info < (3, 12):
        raise AIConfigError("Blooglyblob requires Python 3.12 or newer")
    validate_settings(env)
    key = env.get("OPENAI_API_KEY", "").strip()
    if require_credentials and (not key or key.startswith("your-")):
        raise AIConfigError("OPENAI_API_KEY is required")
    return AIConfig(openai_api_key=key or None)
