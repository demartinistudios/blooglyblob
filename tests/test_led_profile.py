"""Supported physical chain and its software-only diagnostic coverage."""

from blooglyblob.hardware import config, led_controller, test_neopixels
from blooglyblob.hardware.lighting import LightingState, EYE_COLOR, scale
from unittest.mock import Mock


class Strip:
    def __init__(self, count, *settings):
        self.count = count
        self.settings = settings
        self.pixels = {i: (99, 99, 99) for i in range(count)}
        self.frames = []

    def begin(self):
        pass

    def numPixels(self):
        return self.count

    def setPixelColor(self, index, color):
        assert 0 <= index < self.count
        self.pixels[index] = color

    def show(self):
        self.frames.append(self.pixels.copy())


def use_strip(monkeypatch, module):
    monkeypatch.setattr(module, "ON_PI", True)
    monkeypatch.setattr(module, "PixelStrip", Strip, raising=False)
    monkeypatch.setattr(module, "Color", lambda r, g, b: (r, g, b), raising=False)


def test_profile_covers_body_eyes_and_mouth_once():
    assert config.gpio_config.LED_COUNT == 16
    assert list(config.BODY_LEDS) == list(range(6))
    assert list(config.EYE_LEDS) == [6, 7]
    assert list(config.MOUTH_LEDS) == list(range(8, 16))
    assert [*config.BODY_LEDS, *config.EYE_LEDS, *config.MOUTH_LEDS] == list(range(16))


def test_runtime_writes_all_pixels_and_keeps_mouth_dark(monkeypatch):
    use_strip(monkeypatch, led_controller)
    state = LightingState()
    state.set_mode("listening", now=0)
    leds = led_controller.LEDController(state)
    leds._running = True
    monkeypatch.setattr(
        led_controller.time, "sleep", lambda _: setattr(leds, "_running", False)
    )
    leds._animation_loop()
    frame = leds.strip.frames[-1]
    assert any(frame[i] != (0, 0, 0) for i in range(6))
    assert [frame[i] for i in (6, 7)] == [scale(EYE_COLOR, 0.45)] * 2
    assert [frame[i] for i in range(8, 16)] == [(0, 0, 0)] * 8
    leds.stop()
    assert set(leds.strip.frames[-1].values()) == {(0, 0, 0)}


def test_renderer_failure_disables_lights_without_failing_audio(monkeypatch):
    use_strip(monkeypatch, led_controller)
    leds = led_controller.LEDController()
    leds.on_failure = Mock()
    leds.lighting.snapshot = Mock(side_effect=ValueError("bad presentation"))
    leds._running = True
    leds._guarded_loop()
    assert not leds.running
    assert set(leds.strip.frames[-1].values()) == {(0, 0, 0)}
    leds.on_failure.assert_not_called()


def test_native_write_failure_still_uses_hardware_failure_policy(monkeypatch):
    use_strip(monkeypatch, led_controller)
    leds = led_controller.LEDController()
    leds.on_failure = Mock()
    leds.strip.show = Mock(side_effect=OSError("driver failure"))
    leds._running = True
    leds._guarded_loop()
    assert not leds.running
    leds.on_failure.assert_called_once_with("led_worker_failed")


def test_diagnostic_visits_each_pixel_in_order_and_reports_zones(monkeypatch, capsys):
    use_strip(monkeypatch, test_neopixels)
    monkeypatch.setattr(test_neopixels.time, "sleep", lambda _: None)
    strip = test_neopixels.create_strip()
    assert strip.count == 16
    test_neopixels.test_pixel_order(strip)
    lit = [
        [i for i, color in frame.items() if color != (0, 0, 0)]
        for frame in strip.frames
    ]
    assert [pixels for pixels in lit if pixels] == [[i] for i in range(16)]
    assert set(strip.frames[-1].values()) == {(0, 0, 0)}
    output = capsys.readouterr().out
    for index in range(16):
        zone = "body" if index < 6 else "eye" if index < 8 else "mouth"
        assert f"Pixel {index}: {zone}" in output


def test_command_includes_order_check_before_patterns(monkeypatch):
    use_strip(monkeypatch, test_neopixels)
    calls = []
    for name in ("test_pixel_order", "test_solid_colors", "test_patterns"):
        monkeypatch.setattr(
            test_neopixels,
            name,
            lambda strip, name=name: calls.append(name),
            raising=False,
        )
    assert test_neopixels.main() == 0
    assert calls == ["test_pixel_order", "test_solid_colors", "test_patterns"]


def test_diagnostic_interrupt_clears_every_pixel(monkeypatch):
    use_strip(monkeypatch, test_neopixels)
    strip = Strip(16)
    monkeypatch.setattr(test_neopixels, "create_strip", lambda: strip)

    def interrupt_during_mouth(_):
        if strip.pixels[11] != (0, 0, 0):
            raise KeyboardInterrupt

    monkeypatch.setattr(test_neopixels.time, "sleep", interrupt_during_mouth)
    assert test_neopixels.main() == 0
    assert set(strip.frames[-1].values()) == {(0, 0, 0)}


def physical_rgb(frame, index):
    """Decode the driver's GRB bytes as the actual pixel would consume them."""
    red, green, blue = frame[index]
    wire = (green, red, blue)
    if index in config.BODY_LEDS:  # Pebbles consume BGR; face consumes GRB.
        return wire[2], wire[1], wire[0]
    return wire[1], wire[0], wire[2]


def test_runtime_primary_colors_purple_and_amber_match_across_mixed_chain(monkeypatch):
    use_strip(monkeypatch, led_controller)
    leds = led_controller.LEDController()
    for rgb in ((80, 0, 0), (0, 80, 0), (0, 0, 80), (60, 0, 100), (48, 20, 0)):
        for index in range(16):
            leds._set_pixel(index, *rgb)
        assert [physical_rgb(leds.strip.pixels, i) for i in range(16)] == [rgb] * 16


def test_diagnostic_primary_colors_purple_and_amber_match_runtime(monkeypatch):
    use_strip(monkeypatch, test_neopixels)
    monkeypatch.setattr(test_neopixels.time, "sleep", lambda _: None)
    strip = test_neopixels.create_strip()
    for rgb in ((80, 0, 0), (0, 80, 0), (0, 0, 80), (60, 0, 100), (48, 20, 0)):
        test_neopixels.solid_color(strip, *rgb, "regression")
        assert [physical_rgb(strip.pixels, i) for i in range(16)] == [rgb] * 16
