"""NeoPixel LED test patterns for Blooglyblob.

Tests the complete 16-pixel chain:
- One pixel at a time: body 0-5, eyes 6-7, mouth 8-15
- Solid colors (red, green, blue, white)
- Rainbow cycle
- Pulse/breathing effect
- Sparkle effect
- Chase pattern
"""

import colorsys
import time
import sys

# Module entry loads the selected runtime before settings-consuming imports.
if __name__ == "__main__":
    from blooglyblob.config import load_runtime_environment
    load_runtime_environment()

# Only import NeoPixel library when running on Pi
try:
    from rpi_ws281x import PixelStrip, Color, ws
    ON_PI = True
except ImportError:
    ON_PI = False
    print("Note: rpi_ws281x not available - running in simulation mode")

from blooglyblob.hardware.config import BODY_LEDS, EYE_LEDS, MOUTH_LEDS, gpio_config

# NeoPixel configuration for WS2812 (Adafruit 6023 Pebble LEDs)
# WS2812 uses GRB color order at 800kHz
LED_FREQ_HZ = 800000      # LED signal frequency (800kHz)
LED_DMA = 10              # DMA channel for generating signal
LED_INVERT = False        # True to invert the signal
LED_CHANNEL = 0           # PWM channel
LED_STRIP_TYPE = ws.WS2811_STRIP_GRB if ON_PI else None  # WS2812 uses GRB order


def create_strip() -> "PixelStrip":
    """Create and initialize the NeoPixel strip."""
    if not ON_PI:
        return None

    strip = PixelStrip(
        gpio_config.LED_COUNT,
        gpio_config.LED_PIN,
        LED_FREQ_HZ,
        LED_DMA,
        LED_INVERT,
        gpio_config.LED_BRIGHTNESS,
        LED_CHANNEL,
        LED_STRIP_TYPE  # WS2812 GRB color order
    )
    strip.begin()
    return strip


def clear_strip(strip: "PixelStrip"):
    """Turn off all LEDs."""
    if strip is None:
        print("  [SIM] All LEDs off")
        return

    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()


def test_pixel_order(strip: "PixelStrip"):
    """Identify each physical pixel without changing runtime animation behavior."""
    print("\n  Checking DATA ORDER: body 0-5 -> eyes 6-7 -> mouth 8-15")
    clear_strip(strip)
    for zone, indices in (("body", BODY_LEDS), ("eye", EYE_LEDS), ("mouth", MOUTH_LEDS)):
        for index in indices:
            print(f"    Pixel {index}: {zone}", flush=True)
            if strip is not None:
                strip.setPixelColor(index, Color(32, 32, 32))
                strip.show()
            time.sleep(0.5)
            if strip is not None:
                strip.setPixelColor(index, Color(0, 0, 0))
                strip.show()


def solid_color(strip: "PixelStrip", r: int, g: int, b: int, name: str, duration: float = 1.0):
    """Set all LEDs to a solid color."""
    print(f"    {name} ({r}, {g}, {b})")

    if strip is None:
        time.sleep(duration)
        return

    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(r, g, b))
    strip.show()
    time.sleep(duration)


def rainbow_cycle(strip: "PixelStrip", cycles: int = 2, wait_ms: int = 20):
    """Rainbow color cycle across all LEDs."""
    print("    Rainbow cycle...")

    if strip is None:
        time.sleep(cycles * 0.256 * wait_ms / 1000 * 5)
        return

    for j in range(256 * cycles):
        for i in range(strip.numPixels()):
            # Distribute colors evenly across LEDs
            pixel_index = (i * 256 // strip.numPixels()) + j
            strip.setPixelColor(i, wheel(pixel_index & 255))
        strip.show()
        time.sleep(wait_ms / 1000.0)


def wheel(pos: int) -> "Color":
    """Return a fully saturated rainbow color for a 0-255 hue position."""
    red, green, blue = colorsys.hsv_to_rgb(pos / 256, 1, 1)
    return Color(round(red * 255), round(green * 255), round(blue * 255))


def pulse(strip: "PixelStrip", r: int, g: int, b: int, cycles: int = 3, steps: int = 50):
    """Breathing/pulse effect with specified color."""
    print(f"    Pulse effect ({r}, {g}, {b})...")

    if strip is None:
        time.sleep(cycles * steps * 0.02 * 2)
        return

    for _ in range(cycles):
        # Fade in
        for brightness in range(0, steps):
            factor = brightness / steps
            color = Color(int(r * factor), int(g * factor), int(b * factor))
            for i in range(strip.numPixels()):
                strip.setPixelColor(i, color)
            strip.show()
            time.sleep(0.02)

        # Fade out
        for brightness in range(steps, 0, -1):
            factor = brightness / steps
            color = Color(int(r * factor), int(g * factor), int(b * factor))
            for i in range(strip.numPixels()):
                strip.setPixelColor(i, color)
            strip.show()
            time.sleep(0.02)


def sparkle(strip: "PixelStrip", r: int, g: int, b: int, duration: float = 2.0, delay_ms: int = 50):
    """Random sparkle effect."""
    import random
    print(f"    Sparkle effect ({r}, {g}, {b})...")

    if strip is None:
        time.sleep(duration)
        return

    end_time = time.time() + duration
    while time.time() < end_time:
        # Light random pixel
        pixel = random.randint(0, strip.numPixels() - 1)
        strip.setPixelColor(pixel, Color(r, g, b))
        strip.show()
        time.sleep(delay_ms / 1000.0)
        # Turn it off
        strip.setPixelColor(pixel, Color(0, 0, 0))
        strip.show()


def chase(strip: "PixelStrip", r: int, g: int, b: int, cycles: int = 3, wait_ms: int = 50):
    """Theater chase light pattern."""
    print(f"    Chase pattern ({r}, {g}, {b})...")

    if strip is None:
        time.sleep(cycles * 3 * wait_ms / 1000.0 * strip.numPixels() if strip else 1.0)
        return

    for _ in range(cycles):
        for offset in range(3):
            for i in range(strip.numPixels()):
                if (i + offset) % 3 == 0:
                    strip.setPixelColor(i, Color(r, g, b))
                else:
                    strip.setPixelColor(i, Color(0, 0, 0))
            strip.show()
            time.sleep(wait_ms / 1000.0)


def wipe(strip: "PixelStrip", r: int, g: int, b: int, wait_ms: int = 50):
    """Color wipe effect - fills strip one LED at a time."""
    print(f"    Color wipe ({r}, {g}, {b})...")

    if strip is None:
        time.sleep(gpio_config.LED_COUNT * wait_ms / 1000.0)
        return

    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(r, g, b))
        strip.show()
        time.sleep(wait_ms / 1000.0)


def test_solid_colors(strip: "PixelStrip"):
    """Test solid color display."""
    print("\n  Testing SOLID COLORS...")

    solid_color(strip, 255, 0, 0, "Red")
    solid_color(strip, 0, 255, 0, "Green")
    solid_color(strip, 0, 0, 255, "Blue")
    solid_color(strip, 255, 255, 255, "White")
    solid_color(strip, 255, 165, 0, "Orange")
    solid_color(strip, 128, 0, 128, "Purple")

    clear_strip(strip)
    print("    Solid colors complete!")


def test_patterns(strip: "PixelStrip"):
    """Test various LED patterns."""
    print("\n  Testing PATTERNS...")

    # Color wipe
    wipe(strip, 255, 0, 0)
    wipe(strip, 0, 255, 0)
    wipe(strip, 0, 0, 255)
    clear_strip(strip)
    time.sleep(0.3)

    # Rainbow
    rainbow_cycle(strip, cycles=2)
    clear_strip(strip)
    time.sleep(0.3)

    # Pulse
    pulse(strip, 0, 100, 255, cycles=2)
    clear_strip(strip)
    time.sleep(0.3)

    # Sparkle
    sparkle(strip, 255, 255, 255, duration=2.0)
    clear_strip(strip)
    time.sleep(0.3)

    # Chase
    chase(strip, 255, 0, 0, cycles=5)
    clear_strip(strip)

    print("    Patterns complete!")


def main():
    """Run the NeoPixel test sequence."""
    print("=" * 50)
    print("  BLOOGLYBLOB NEOPIXEL TEST")
    print("=" * 50)
    print()
    print(f"  LED Pin:    GPIO {gpio_config.LED_PIN}")
    print(f"  LED Count:  {gpio_config.LED_COUNT}")
    print(f"  Brightness: {gpio_config.LED_BRIGHTNESS}/255")
    print()
    print("=" * 50)

    strip = None

    try:
        # Initialize strip
        print("\nInitializing NeoPixel strip...")
        strip = create_strip()

        if ON_PI:
            print("  Strip initialized!")
        else:
            print("  Running in simulation mode (not on Pi)")

        # Test sequence
        print("\n" + "=" * 50)
        print("  STARTING TEST SEQUENCE")
        print("=" * 50)

        test_pixel_order(strip)

        # Test solid colors
        test_solid_colors(strip)

        # Test patterns
        test_patterns(strip)

        print("\n" + "=" * 50)
        print("  TEST SEQUENCE COMPLETE!")
        print("=" * 50)

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\nError during test: {e}")
        return 1
    finally:
        print("\nCleaning up...")
        if strip:
            clear_strip(strip)
        print("Done!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
