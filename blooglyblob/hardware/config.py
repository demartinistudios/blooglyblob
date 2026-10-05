"""GPIO assignments; runtime settings are loaded by the application."""
from dataclasses import dataclass


# One data chain; F2 protects lighting, with a dedicated head power pair.
BODY_LEDS = range(0, 6)
EYE_LEDS = range(6, 8)
MOUTH_LEDS = range(8, 16)


@dataclass
class GPIOConfig:
    """GPIO pin mappings (adjust based on your wiring)."""
    # Arm servos (hardware PWM pins)
    LEFT_ARM_PIN: int = 12   # GPIO 12 (hardware PWM channel 0)
    RIGHT_ARM_PIN: int = 13  # GPIO 13 (hardware PWM channel 1)
    # Head servo (DMA-timed PWM via pigpio)
    HEAD_PIN: int = 16       # GPIO 16

    # NeoPixel LED strip
    LED_PIN: int = 18        # GPIO 18 (PWM channel 0)
    LED_COUNT: int = 16      # Body 0-5, separate eyes 6-7, mouth 8-15
    LED_BRIGHTNESS: int = 128  # 0-255 (half brightness)

    # Button for push-to-talk
    BUTTON_PIN: int = 17     # GPIO 17



gpio_config = GPIOConfig()
