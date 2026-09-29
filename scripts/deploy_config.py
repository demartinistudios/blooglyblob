"""Small, non-executable configuration format shared by deployment helpers."""

from pathlib import Path
import math
import re


def parse_value(value: str) -> str:
    value = value.strip()
    if not value.startswith(("'", '"')):
        return re.sub(r"\s+#.*$", "", value).rstrip()
    quote = value[0]
    pattern = r"'((?:\\'|[^'])*)'" if quote == "'" else r'"((?:\\"|[^"])*)"'
    match = re.match(pattern, value)
    if not match or (
        value[match.end() :].strip()
        and not value[match.end() :].strip().startswith("#")
    ):
        raise ValueError("Invalid quoted value")
    # Match python-dotenv's single-line quoting (including set_key's \\' escape),
    # without expansion. In particular ${NAME} and $(command) remain literal.
    escapes = (
        {"\\": "\\", "'": "'"}
        if quote == "'"
        else {
            "\\": "\\",
            '"': '"',
            "a": "\a",
            "b": "\b",
            "f": "\f",
            "n": "\n",
            "r": "\r",
            "t": "\t",
            "v": "\v",
            "'": "'",
        }
    )
    return re.sub(r"\\(.)", lambda found: escapes.get(found[1], found[0]), match[1])


def read_env(path: Path) -> dict[str, str]:
    """Read single-line KEY=value data, without interpolation or shell execution.

    Quoted values and trailing comments are supported. Errors name the line,
    never its contents (which may contain credentials).
    """
    values = {}
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"{path.name}: invalid assignment at line {number}")
        try:
            values[key] = parse_value(value)
        except ValueError:
            raise ValueError(f"{path.name}: invalid quoting at line {number}") from None
    return values


def serialize_env(values: dict[str, str]) -> str:
    """Single physical line per assignment, literal in both supported parsers."""
    escapes = {
        "\\": "\\\\",
        '"': '\\"',
        "\n": "\\n",
        "\r": "\\r",
        "\t": "\\t",
        "\a": "\\a",
        "\b": "\\b",
        "\f": "\\f",
        "\v": "\\v",
    }
    lines = []
    for key, value in values.items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) or "\x00" in value:
            raise ValueError("Invalid environment assignment")
        encoded = "".join(escapes.get(char, char) for char in value)
        lines.append(f'{key}="{encoded}"\n')
    return "".join(lines)


def private_candidate(
    directory: Path, values: dict[str, str], *, owner: tuple[int, int] | None = None
) -> Path:
    """Set owner and 0600 before the first content write; clean failed candidates."""
    import os
    import tempfile

    content = serialize_env(values)
    directory.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".app-env-", dir=directory)
    path = Path(name)
    try:
        with os.fdopen(fd, "w") as stream:
            if owner is not None:
                os.fchown(stream.fileno(), *owner)
            os.fchmod(stream.fileno(), 0o600)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def sync_directory(directory: Path) -> None:
    import os

    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def update_env(path: Path, updates: dict[str, str]) -> None:
    """Privately replace helper settings, preserving owner and unrelated values."""
    import os

    values = read_env(path) if path.exists() else {}
    previous = path.stat() if path.exists() else None
    owner = (previous.st_uid, previous.st_gid) if previous else None
    candidate = private_candidate(path.parent, values | updates, owner=owner)
    try:
        os.replace(candidate, path)
        sync_directory(path.parent)
    finally:
        candidate.unlink(missing_ok=True)


def selected_runtime_file() -> Path:
    """Interactive helpers may use the documented developer runtime input."""
    import os

    return Path(
        os.environ.get(
            "BLOOGLYBLOB_ENV_FILE",
            Path(__file__).resolve().parents[1] / "config" / "app.env",
        )
    )


def validate_runtime_config(values: dict[str, str]) -> None:
    """Preflight without the runtime package or its dependencies in staged installs."""
    key = values.get("OPENAI_API_KEY", "").strip()
    if not key or key.startswith("your-"):
        raise ValueError("OPENAI_API_KEY is required in app.env")
    for key in ("MIC_GAIN", "OPENAI_INACTIVITY_SECONDS", "OPENAI_SESSION_MAX_SECONDS"):
        if key in values:
            try:
                number = int(values[key]) if key == "MIC_GAIN" else float(values[key])
                if not math.isfinite(number) or (key != "MIC_GAIN" and number <= 0):
                    raise ValueError
            except (ValueError, OverflowError):
                raise ValueError(
                    f"{key} must be a finite number"
                    if key == "MIC_GAIN"
                    else f"{key} must be positive and finite"
                ) from None
    for key in (
        "BLOOGLYBLOB_STATE_DIR",
        "SERVO_CALIBRATION_FILE",
        "BLOOGLYBLOB_MEDIA_DIR",
    ):
        if key in values and not values[key].strip():
            raise ValueError(f"{key} must name a path")


def read_runtime_config(path: Path) -> dict[str, str]:
    try:
        values = read_env(path)
    except (OSError, UnicodeError):
        raise ValueError(f"Cannot read configuration {path}") from None
    validate_runtime_config(values)
    return values


def ensure_runtime_config(
    destination: Path,
    staged_file: Path | None = None,
    *,
    owner: tuple[int, int] | None = None,
) -> dict[str, str]:
    """Keep existing settings; publish fresh settings privately without overwrite.

    Run under the installation lock before stopping the application. A valid
    file that appears during publication wins and is validated before use.
    """
    import os

    if not destination.exists():
        if staged_file is None or not staged_file.is_file():
            raise ValueError(
                "Missing app.env; select BLOOGLYBLOB_ENV_FILE before provisioning"
            )
        candidate = private_candidate(
            destination.parent, read_runtime_config(staged_file), owner=owner
        )
        try:
            try:
                os.link(candidate, destination)
            except FileExistsError:
                pass
        finally:
            candidate.unlink(missing_ok=True)
    values = read_runtime_config(destination)
    if owner is not None:
        os.chown(destination, *owner)
    destination.chmod(0o600)
    sync_directory(destination.parent)
    return values
