"""Exercise the real SDK independently of legacy tests' global SDK mocks."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_roku_sdk_calls_have_a_finite_network_timeout(method):
    program = """
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

from blooglyblob.tools.roku_controller import RokuController

method = sys.argv[1]
with patch.object(RokuController, '_build_channel_ids', lambda self: None):
    controller = RokuController('192.0.2.1')
connection = SimpleNamespace(get=Mock(), post=Mock())
operation = getattr(connection, method.lower())
operation.return_value = SimpleNamespace(status_code=200, content=b'ok')
controller.roku._conn = connection
assert controller.roku._call(method, '/query/apps') == b'ok'
assert operation.call_args.kwargs['timeout'] == 5.0
"""
    result = subprocess.run(
        [sys.executable, "-c", program, method],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
