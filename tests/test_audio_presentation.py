"""Visual observations never confer audio ownership or completion."""

import math
from blooglyblob.audio.presentation import OutputPresentation, OutputTimeline


def test_replacement_rejects_late_write_and_late_clear():
    out = OutputPresentation()
    old = out.begin("speech")
    new = out.begin("music")
    out.commit(new, start=1, end=1.1, position=4, level=0)
    out.commit(old, start=1, end=1.1, position=0, level=1)
    out.retire(old)
    assert out.sample(1.05).kind == "music"
    assert math.isclose(out.sample(1.05).position, 4.05)
    out.retire(new)
    assert out.sample(1.05).kind is None


def test_intervals_do_not_free_run_across_stalls():
    out = OutputPresentation()
    owner = out.begin("speech")
    out.commit(owner, start=2, end=2.02, position=0, level=0.8)
    assert out.sample(1).level == 0
    assert out.sample(2.01).level == 0.8
    assert out.sample(2.03).level == 0


def test_unknown_latency_disables_visuals_only():
    out = OutputPresentation()
    owner = out.begin("speech")
    clock = iter([1.0, 1.02])
    timeline = OutputTimeline(object(), 48000, out, owner, clock=lambda: next(clock))
    timeline.before_write()
    timeline.written(960, 0.8)
    assert out.sample(1.03).kind is None


def test_timeline_is_bounded_and_reanchors_after_gap():
    class Stream:
        def get_output_latency(self):
            return 0.05

    out = OutputPresentation()
    owner = out.begin("music")
    ticks = iter([1.0, 1.001, 2.0, 2.001])
    timeline = OutputTimeline(Stream(), 48000, out, owner, clock=lambda: next(ticks))
    timeline.before_write()
    timeline.written(960)
    assert math.isclose(out.sample(1.06).position, 0.01)
    assert out.sample(1.5).kind is None
    timeline.before_write()
    timeline.written(960)
    assert math.isclose(out.sample(2.06).position, 0.03)


def test_overflow_drops_visuals_instead_of_extending_memory():
    out = OutputPresentation()
    owner = out.begin("speech")
    for i in range(200):
        out.commit(
            owner,
            start=10 + i * 0.001,
            end=10 + (i + 1) * 0.001,
            position=0,
            level=0.5,
            now=10,
        )
    assert out.sample(10.15).kind is None


def test_observer_error_cannot_escape_into_writer():
    class Stream:
        def get_output_latency(self):
            return 0.05

    out = OutputPresentation()
    owner = out.begin("speech")
    ticks = iter([1.0, 1.02])
    timeline = OutputTimeline(Stream(), 48000, out, owner, clock=lambda: next(ticks))

    def broken(*args, **kwargs):
        raise RuntimeError("visual failure")

    out.commit = broken
    timeline.before_write()
    timeline.written(960, 0.8)
    assert out.sample(1.06).kind is None


def test_music_uses_native_frame_count_and_partial_tail():
    class Stream:
        def get_output_latency(self):
            return 0.05

    ticks = iter([1.0, 1.0, 1.0, 1.0])
    out = OutputPresentation()
    owner = out.begin("music")
    timeline = OutputTimeline(Stream(), 44100, out, owner, clock=lambda: next(ticks))
    timeline.before_write()
    timeline.written(1024)
    timeline.before_write()
    timeline.written(100)
    assert math.isclose(out.sample(1.05 + 1050 / 44100).position, 1050 / 44100)
    assert out.sample(1.05 + 1125 / 44100).kind is None
