"""One 30 fps writer for the body, eyes and mouth NeoPixel chain."""

import logging
import threading
import time

try:
    from rpi_ws281x import PixelStrip, Color, ws

    ON_PI = True
except ImportError:
    ON_PI = False

    def Color(r, g, b):
        return (r, g, b)


from .config import gpio_config
from .lighting import LightingState, render

# WS2812/NeoPixel GRB chain; Adafruit 6026 body lights, 5975 eyes, 1426 mouth.
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_INVERT = False
LED_CHANNEL = 0
LED_STRIP_TYPE = ws.WS2811_STRIP_GRB if ON_PI else None


class LEDController:
    def __init__(self, lighting=None):
        self.strip = None
        self._running = False
        self._closed = False
        self._thread = None
        self.lighting = lighting if lighting is not None else LightingState()

        # Initialize strip
        if ON_PI:
            try:
                self.strip = PixelStrip(
                    gpio_config.LED_COUNT,
                    gpio_config.LED_PIN,
                    LED_FREQ_HZ,
                    LED_DMA,
                    LED_INVERT,
                    gpio_config.LED_BRIGHTNESS,
                    LED_CHANNEL,
                    LED_STRIP_TYPE,
                )
                self.strip.begin()
                print("  LED strip initialized!")
            except Exception as e:
                print(f"  Warning: Could not initialize LED strip: {e}")
                self.strip = None
        else:
            print("  LED strip in simulation mode (not on Pi)")

    @property
    def running(self):
        return self._running

    def start(self):
        """Start the ambient pattern animation thread."""
        if self._running or self._closed:
            return

        self._running = True
        self._thread = threading.Thread(target=self._guarded_loop, daemon=True)
        self._thread.start()
        print("  LED ambient patterns started!")

    def stop(self):
        """Stop the animation and turn off all LEDs."""
        self.lighting.stop()
        self._closed = True
        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            if self._thread.is_alive():
                raise RuntimeError("Hardware worker release not confirmed")

        self._clear_all()
        print("  LED controller stopped")

    def _clear_all(self):
        """Turn off all LEDs."""
        if self.strip is None:
            return

        for i in range(self.strip.numPixels()):
            self.strip.setPixelColor(i, Color(0, 0, 0))
        self.strip.show()

    def _set_pixel(self, index: int, r: int, g: int, b: int):
        """Set a single pixel color."""
        if self.strip is None:
            return
        self.strip.setPixelColor(index, Color(r, g, b))

    def _show(self):
        """Update the LED strip display."""
        if self.strip is None:
            return
        self.strip.show()

    def _guarded_loop(self):
        try:
            self._animation_loop()
        except Exception:
            self._running = False
            callback = getattr(self, "on_failure", None)
            if callback:
                callback("led_worker_failed")
            else:
                print("led_worker_failed")

    def _animation_loop(self):
        while self._running:
            start = time.monotonic()
            try:
                frame = render(self.lighting.snapshot(start), start)
            except Exception:
                # Pure presentation is optional. Physical clear failures still
                # reach the native failure/ownership path in _guarded_loop.
                logging.getLogger(__name__).warning("Lighting renderer disabled")
                self._running = False
                self._clear_all()
                return
            for index, color in enumerate(frame):
                self._set_pixel(index, *color)
            self._show()
            time.sleep(max(0.0, 1.0 / 30 - (time.monotonic() - start)))

    def cleanup(self):
        self.stop()
