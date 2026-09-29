"""Tests for network integration and timer tool handlers.

Integration owners are injected mocks; dependency modules remain real.
"""

import json
import tempfile
import subprocess
import sys
from pathlib import Path
import unittest
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from blooglyblob.tools.handlers import (
    ToolHandlers,
    create_stream_content_handler,
    create_roku_control_handler,
    create_timer_handlers,
)
from blooglyblob.tools.timer_manager import TimerManager


# Minimal dataclasses to replace content_search types
@dataclass
class ContentResult:
    """Mock ContentResult for tests."""

    tmdb_id: int
    title: str
    media_type: str
    year: int | None


@dataclass
class Episode:
    """Mock Episode for tests."""

    season: int
    number: int
    name: str
    overview: str | None


class TestStreamContentHandler(unittest.TestCase):
    """Tests for streamContent tool handler."""

    def test_no_content_search_returns_error(self):
        """Missing content_search returns error."""
        handler = create_stream_content_handler(None, MagicMock())
        result = handler({"title": "test"})
        self.assertIn("Error", result)

    def test_no_roku_controller_returns_error(self):
        """Missing roku_controller returns error."""
        handler = create_stream_content_handler(MagicMock(), None)
        result = handler({"title": "test"})
        self.assertIn("Error", result)

    def test_missing_title_returns_error(self):
        """Missing title returns error."""
        mock_content = MagicMock()
        mock_roku = MagicMock()
        handler = create_stream_content_handler(mock_content, mock_roku)

        result = handler({})
        self.assertIn("Error", result)

    def test_content_not_found_returns_message(self):
        """Content not found returns helpful message."""
        mock_content = MagicMock()
        mock_content.search.return_value = None
        mock_roku = MagicMock()
        handler = create_stream_content_handler(mock_content, mock_roku)

        result = handler({"title": "nonexistent movie"})
        self.assertIn("Couldn't find", result)

    def test_successful_movie_launch(self):
        """Movie found and launched successfully."""
        mock_content = MagicMock()
        mock_content.search.return_value = ContentResult(
            tmdb_id=123, title="Test Movie", media_type="movie", year=2024
        )
        mock_content.get_streaming_links.return_value = {
            "netflix": {"content_id": "abc123", "url": ""}
        }

        mock_roku = MagicMock()
        mock_roku.launch_with_content.return_value = True

        handler = create_stream_content_handler(mock_content, mock_roku)
        result = handler({"title": "Test Movie"})

        self.assertIn("Playing", result)
        self.assertIn("netflix", result)
        mock_roku.launch_with_content.assert_called_once()

    def test_tv_show_with_random_episode(self):
        """TV show with random episode selection."""
        mock_content = MagicMock()
        mock_content.search.return_value = ContentResult(
            tmdb_id=456, title="Test Show", media_type="tv", year=2023
        )
        mock_content.get_random_episode.return_value = Episode(
            season=2, number=5, name="Episode Title", overview="Description"
        )
        mock_content.get_streaming_links.return_value = {
            "disney+": {"content_id": "xyz789", "url": ""}
        }
        mock_content.watchmode_api_key = None

        mock_roku = MagicMock()
        mock_roku.launch_with_content.return_value = True

        handler = create_stream_content_handler(mock_content, mock_roku)
        result = handler({"title": "Test Show", "random_episode": True})

        self.assertIn("S2E5", result)
        mock_content.get_random_episode.assert_called_once()

    def test_specific_service_not_available(self):
        """Specific service requested but not available."""
        mock_content = MagicMock()
        mock_content.search.return_value = ContentResult(
            tmdb_id=789, title="Movie", media_type="movie", year=2024
        )
        mock_content.get_streaming_links.return_value = {
            "hulu": {"content_id": "hulu123", "url": ""}
        }

        mock_roku = MagicMock()
        handler = create_stream_content_handler(mock_content, mock_roku)

        result = handler({"title": "Movie", "service": "netflix"})
        self.assertIn("isn't on netflix", result)
        self.assertIn("hulu", result)


class TestRokuControlHandler(unittest.TestCase):
    """Tests for rokuControl tool handler."""

    def test_no_controller_returns_error(self):
        """Missing controller returns error."""
        handler = create_roku_control_handler(None)
        result = handler({"action": "volume_up"})
        self.assertIn("Error", result)

    def test_volume_up_success(self):
        """Volume up action succeeds."""
        mock_roku = MagicMock()
        mock_roku.volume_up.return_value = True
        handler = create_roku_control_handler(mock_roku)

        result = handler({"action": "volume_up"})
        self.assertIn("Done", result)
        mock_roku.volume_up.assert_called_once()

    def test_play_pause_success(self):
        """Play/pause action succeeds."""
        mock_roku = MagicMock()
        mock_roku.play_pause.return_value = True
        handler = create_roku_control_handler(mock_roku)

        result = handler({"action": "play_pause"})
        self.assertIn("Done", result)

    def test_launch_app_success(self):
        """Launch app action succeeds."""
        mock_roku = MagicMock()
        mock_roku.launch_app.return_value = True
        handler = create_roku_control_handler(mock_roku)

        result = handler({"action": "launch_app", "app": "Netflix"})
        self.assertIn("Launched Netflix", result)

    def test_launch_app_missing_name(self):
        """Launch app without name returns error."""
        mock_roku = MagicMock()
        handler = create_roku_control_handler(mock_roku)

        result = handler({"action": "launch_app"})
        self.assertIn("Error", result)

    def test_unknown_action(self):
        """Unknown action returns error."""
        mock_roku = MagicMock()
        handler = create_roku_control_handler(mock_roku)

        result = handler({"action": "do_a_flip"})
        self.assertIn("Unknown", result)


class TestTimerHandlers(unittest.TestCase):
    """Tests for timer tool handlers."""

    def setUp(self):
        """Create temporary directory for timer storage."""
        self.temp_dir = tempfile.mkdtemp()
        self.timer_manager = TimerManager(alert_callback=None, data_dir=self.temp_dir)

    def tearDown(self):
        """Clean up timer manager and temp files."""
        self.timer_manager.stop()
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_set_timer_no_manager_returns_error(self):
        """Missing timer manager returns error."""
        set_timer, _, _ = create_timer_handlers(None)
        result = set_timer({"duration_seconds": 60})
        self.assertIn("Error", result)

    def test_set_timer_invalid_duration(self):
        """Invalid duration returns error."""
        set_timer, _, _ = create_timer_handlers(self.timer_manager)
        result = set_timer({"duration_seconds": 0})
        self.assertIn("Error", result)

    def test_set_timer_success(self):
        """Set timer succeeds."""
        set_timer, _, _ = create_timer_handlers(self.timer_manager)

        result = set_timer({"duration_seconds": 300, "label": "pizza"})
        self.assertIn("5 minute", result)
        self.assertIn("pizza", result)

        # Verify timer was added
        timers = self.timer_manager.get_active_timers()
        self.assertEqual(len(timers), 1)
        self.assertEqual(timers[0].label, "pizza")

    def test_set_timer_hours_formatting(self):
        """Timer with hours formats correctly."""
        set_timer, _, _ = create_timer_handlers(self.timer_manager)

        result = set_timer({"duration_seconds": 3900})  # 1h 5m
        self.assertIn("1 hour", result)
        self.assertIn("5 minute", result)

    def test_cancel_timer_not_found(self):
        """Cancel nonexistent timer returns message."""
        _, cancel_timer, _ = create_timer_handlers(self.timer_manager)

        result = cancel_timer({"timer_id": "nonexistent"})
        self.assertIn("not found", result)

    def test_cancel_timer_success(self):
        """Cancel timer succeeds."""
        set_timer, cancel_timer, _ = create_timer_handlers(self.timer_manager)

        # Add timer
        set_timer({"duration_seconds": 60, "label": "test"})
        timers = self.timer_manager.get_active_timers()
        timer_id = timers[0].id

        # Cancel it
        result = cancel_timer({"timer_id": timer_id})
        self.assertIn("cancelled", result.lower())

        # Verify removed
        self.assertEqual(len(self.timer_manager.get_active_timers()), 0)

    def test_cancel_all_timers(self):
        """Cancel all timers succeeds."""
        set_timer, cancel_timer, _ = create_timer_handlers(self.timer_manager)

        # Add multiple timers
        set_timer({"duration_seconds": 60, "label": "one"})
        set_timer({"duration_seconds": 120, "label": "two"})

        # Cancel all
        result = cancel_timer({"timer_id": "all"})
        self.assertIn("2 timer", result)
        self.assertEqual(len(self.timer_manager.get_active_timers()), 0)

    def test_find_timers_no_active(self):
        """Find timers with none active returns message."""
        _, _, find_timers = create_timer_handlers(self.timer_manager)

        result = find_timers({"queries": []})
        self.assertIn("No active", result)

    def test_find_timers_lists_all(self):
        """Find timers without query lists all."""
        set_timer, _, find_timers = create_timer_handlers(self.timer_manager)

        set_timer({"duration_seconds": 60, "label": "pizza"})
        set_timer({"duration_seconds": 120, "label": "laundry"})

        result = find_timers({"queries": []})
        data = json.loads(result)

        self.assertEqual(len(data), 2)
        labels = {t["label"] for t in data}
        self.assertIn("pizza", labels)
        self.assertIn("laundry", labels)

    def test_find_timers_with_query(self):
        """Find timers with query filters results."""
        set_timer, _, find_timers = create_timer_handlers(self.timer_manager)

        set_timer({"duration_seconds": 60, "label": "pizza timer"})
        set_timer({"duration_seconds": 120, "label": "laundry"})

        result = find_timers({"queries": ["pizza", "pie"]})
        data = json.loads(result)

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["label"], "pizza timer")

    def test_find_timers_no_match(self):
        """Find timers with no matches returns message."""
        set_timer, _, find_timers = create_timer_handlers(self.timer_manager)

        set_timer({"duration_seconds": 60, "label": "pizza"})

        result = find_timers({"queries": ["laundry"]})
        self.assertIn("No timers matching", result)


class TestToolHandlersClass(unittest.TestCase):
    """Tests for ToolHandlers container class."""

    def test_get_handler_returns_callable(self):
        """get_handler returns callable for known tools."""
        handlers = ToolHandlers()

        handler = handlers.get_handler("setTimer")
        self.assertIsNotNone(handler)
        self.assertTrue(callable(handler))

    def test_get_handler_unknown_returns_none(self):
        """get_handler returns None for unknown tools."""
        handlers = ToolHandlers()

        handler = handlers.get_handler("unknownTool")
        self.assertIsNone(handler)

    def test_handle_unknown_tool_returns_error(self):
        """handle() with unknown tool returns error."""
        handlers = ToolHandlers()

        result = handlers.handle("unknownTool", {})
        self.assertIn("Error", result)
        self.assertIn("Unknown tool", result)

    def test_handle_calls_correct_handler(self):
        """handle() routes to correct handler."""
        handlers = ToolHandlers()

        with patch.object(handlers, "set_timer", return_value="set") as timer:
            self.assertEqual(
                handlers.handle("setTimer", {"duration_seconds": 60}), "set"
            )
            timer.assert_called_once_with({"duration_seconds": 60})


if __name__ == "__main__":
    unittest.main()


def test_collection_preserves_real_integration_modules():
    """Collecting handler tests must not replace dependencies for other suites."""
    program = """
import sys
import rapidfuzz, rapidfuzz.fuzz, tmdbv3api, roku
modules = {name: sys.modules[name] for name in ('rapidfuzz', 'rapidfuzz.fuzz', 'tmdbv3api', 'roku')}
paths = list(sys.path)
import tests.test_tool_handlers
assert sys.path == paths
assert all(sys.modules[name] is module for name, module in modules.items())
assert rapidfuzz.fuzz.ratio('same', 'same') == 100
"""
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
