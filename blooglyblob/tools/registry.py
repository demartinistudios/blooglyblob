"""Tool schemas shared by validation and OpenAI Responses."""

import json
from importlib.resources import files
from pathlib import Path

HARDWARE_TOOLS = frozenset({"playAnimation", "moveHead", "goToSleep", "danceMode"})


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, dict] = {}

    def load_from_configs(self, config_dir=None):
        root = Path(config_dir) if config_dir else files("tool_configs")
        for path in sorted(root.iterdir(), key=lambda path: path.name):
            if path.name.endswith(".json"):
                config = json.loads(path.read_text())
                self._tools[config["name"]] = {
                    key: config[key] for key in ("name", "description", "input_schema")
                }

    def schemas(self):
        return list(self._tools.values())

    @property
    def tool_names(self):
        return list(self._tools)
