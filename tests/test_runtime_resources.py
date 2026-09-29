"""Installed resources and persistent state must not depend on a checkout."""

import json

from blooglyblob.tools.timer_manager import TimerManager


def test_timers_use_explicit_state_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("BLOOGLYBLOB_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.chdir(tmp_path)
    timers = TimerManager()
    timer_id = timers.add_timer(3600, "test")
    stored = json.loads((tmp_path / "state" / "timers.json").read_text())
    assert stored["timers"][0]["id"] == timer_id
    assert not (tmp_path / "data").exists()


def test_failed_timer_replace_preserves_previous_file(monkeypatch, tmp_path):
    timers = TimerManager(data_dir=str(tmp_path))
    timers.add_timer(3600, "original")
    original = (tmp_path / "timers.json").read_bytes()

    def fail_replace(*args):
        raise OSError("interrupted write")

    monkeypatch.setattr("blooglyblob.tools.timer_manager.os.replace", fail_replace)
    timers.add_timer(3600, "new")
    assert (tmp_path / "timers.json").read_bytes() == original


def test_restart_discards_overdue_timers_without_replaying_alerts(
    monkeypatch, tmp_path
):
    now = 1000.0
    monkeypatch.setattr("blooglyblob.tools.timer_manager.time.time", lambda: now)
    original = TimerManager(data_dir=str(tmp_path))
    original.add_timer(5, "expired")
    retained = original.add_timer(60, "upcoming")
    now += 10
    alerts = []
    restarted = TimerManager(alert_callback=alerts.append, data_dir=str(tmp_path))
    assert [timer.id for timer in restarted.get_active_timers()] == [retained]
    restarted._check_timers()
    assert alerts == []
    stored = json.loads((tmp_path / "timers.json").read_text())
    assert [timer["id"] for timer in stored["timers"]] == [retained]
    now += 60
    restarted._check_timers()
    restarted._check_timers()
    assert [timer.id for timer in alerts] == [retained]
    assert restarted.get_active_timers() == []


def test_packaged_tool_configs_load_outside_checkout(monkeypatch, tmp_path):
    from blooglyblob.tools.registry import ToolRegistry

    monkeypatch.chdir(tmp_path)
    registry = ToolRegistry()
    registry.load_from_configs()
    assert {"goToSleep", "danceMode", "setTimer"} <= set(registry.tool_names)


def test_producer_stop_preserves_unconfirmed_thread_ownership(tmp_path):
    from unittest.mock import Mock
    import pytest
    from blooglyblob.tools.ring_handler import RingHandler

    for component in (TimerManager(data_dir=str(tmp_path)), RingHandler(lambda: None)):
        worker = Mock()
        worker.is_alive.return_value = True
        component._thread = worker
        with pytest.raises(RuntimeError, match="release unconfirmed"):
            component.stop()
        assert component._thread is worker
        worker.join.assert_called_once()


def test_doorbell_callback_runs_on_owned_poller_without_new_thread(monkeypatch):
    from unittest.mock import Mock
    from blooglyblob.tools import ring_handler

    callback = Mock()
    handler = ring_handler.RingHandler(callback, debounce_seconds=0)
    factory = Mock(side_effect=AssertionError("No unowned callback worker"))
    monkeypatch.setattr(ring_handler.threading, "Thread", factory)
    handler._handle_ding()
    callback.assert_called_once()
    factory.assert_not_called()


def test_bundled_lights_match_native_song_and_deployment_payload():
    from importlib.resources import files, as_file
    from blooglyblob.hardware.music_lights import load_lights
    from scripts.deploy import MEDIA

    with as_file(files("songs").joinpath("dance_song.wav")) as wav:
        with as_file(files("songs").joinpath("dance_song_lights.json")) as sidecar:
            lights = load_lights(wav, sidecar)
    assert lights is not None
    assert len(lights.frames) == 5400 * 8
    assert "songs/dance_song_lights.json" in MEDIA
    # Loud sections retain accents: the whole row is never held above .6.
    assert not any(
        all(v > 153 for v in lights.frames[i : i + 8])
        for i in range(0, len(lights.frames), 8)
    )
