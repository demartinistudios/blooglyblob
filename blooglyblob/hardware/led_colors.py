"""Encode the mixed NeoPixel chain through the driver's GRB transport.

Body 0–5: Adafruit 6026 pebble/seed pixels, BGR byte order.
Eyes 6–7: Adafruit 5975 breakouts, GRB byte order.
Mouth 8–15: Adafruit 1426 RGB stick, GRB byte order.
All consume three bytes per pixel at 800 kHz; none is RGBW.

Pebble reference: https://learn.adafruit.com/midi-neopixel-visualizer/code
Eye reference: https://learn.adafruit.com/adafruit-neopixel-breakout/arduino
Mouth reference: https://www.adafruit.com/product/1426
"""

from .config import BODY_LEDS


def driver_rgb(index: int, red: int, green: int, blue: int) -> tuple[int, int, int]:
    """Keep rendering in RGB; adapt only the physical driver's input channels."""
    if index in BODY_LEDS:
        # GRB transport sends (argument2, argument1, argument3).
        # These arguments therefore produce the pebble's required (B, G, R).
        return green, blue, red
    return red, green, blue
