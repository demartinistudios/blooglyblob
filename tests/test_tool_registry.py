"""Tool schema loading survives package reorganization."""

import json
import os
import tempfile
import unittest

from blooglyblob.tools.registry import ToolRegistry, HARDWARE_TOOLS


class TestToolClassification(unittest.TestCase):
    def test_hardware_tools_defined(self):
        """Hardware tools should include Pi-specific tools."""
        self.assertIn("playAnimation", HARDWARE_TOOLS)
        self.assertIn("moveHead", HARDWARE_TOOLS)
        self.assertIn("goToSleep", HARDWARE_TOOLS)
        self.assertIn("danceMode", HARDWARE_TOOLS)
        self.assertEqual(len(HARDWARE_TOOLS), 4)


class TestToolRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()

    def test_load_from_configs(self):
        """Should load tools from config directory."""
        config_dir = os.path.join(os.path.dirname(__file__), "..", "tool_configs")
        self.registry.load_from_configs(config_dir)
        # Should have loaded tools
        self.assertGreater(len(self.registry.tool_names), 0)
        self.assertIn("playAnimation", self.registry.tool_names)

    def test_load_from_temp_configs(self):
        """Should load tools from custom directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "name": "testTool",
                "description": "Test tool",
                "input_schema": {"type": "object", "properties": {}},
            }
            with open(os.path.join(tmpdir, "testTool.json"), "w") as f:
                json.dump(config, f)

            self.registry.load_from_configs(tmpdir)
            self.assertIn("testTool", self.registry.tool_names)

    def test_loads_native_schema_format(self):
        """Should load native schema format directly without conversion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "name": "myTool",
                "description": "Does something",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "arg1": {"type": "string", "description": "Argument 1"}
                    },
                    "required": ["arg1"],
                },
            }
            with open(os.path.join(tmpdir, "myTool.json"), "w") as f:
                json.dump(config, f)

            self.registry.load_from_configs(tmpdir)
            tools = self.registry.schemas()
            self.assertEqual(len(tools), 1)
            self.assertEqual(tools[0]["name"], "myTool")
            self.assertEqual(tools[0]["description"], "Does something")
            self.assertEqual(tools[0]["input_schema"]["type"], "object")
            self.assertEqual(tools[0]["input_schema"]["required"], ["arg1"])

    def test_schemas(self):
        """Should return tools as input schemas."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "name": "testTool",
                "description": "Test",
                "input_schema": {"type": "object", "properties": {}},
            }
            with open(os.path.join(tmpdir, "testTool.json"), "w") as f:
                json.dump(config, f)

            self.registry.load_from_configs(tmpdir)
            tools = self.registry.schemas()
            self.assertEqual(len(tools), 1)
            self.assertEqual(tools[0]["name"], "testTool")
            self.assertIn("input_schema", tools[0])
