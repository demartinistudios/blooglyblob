"""Thread-safe shared state for conversation mode and audio levels.

Used to coordinate between audio processing and LED patterns.
"""

import threading
from enum import Enum


class ConversationMode(Enum):
    """Current conversation state for LED pattern selection."""

    IDLE = "idle"  # Not in conversation - calm ambient pattern
    LISTENING = "listening"  # Waiting for user input - cyan/blue pulse
    PROCESSING = "processing"  # STT/LLM processing - thinking
    SPEAKING = "speaking"  # Agent responding - orange/yellow, audio-reactive
    DANCING = "dancing"  # Dance mode active
    ALERT = "alert"  # Timer firing - fast red pulse, urgent


class ConversationState:
    """Thread-safe container for conversation state shared between audio and LEDs.

    Attributes:
        mode: Current conversation mode (IDLE, LISTENING, SPEAKING)
        audio_level: Audio amplitude 0.0-1.0 for reactive LED brightness
    """

    def __init__(self):
        """Initialize with IDLE state and zero audio level."""
        self._lock = threading.Lock()
        self._mode = ConversationMode.IDLE
        self._audio_level = 0.0

    @property
    def mode(self) -> ConversationMode:
        """Get current conversation mode."""
        with self._lock:
            return self._mode

    @mode.setter
    def mode(self, value: ConversationMode) -> None:
        """Set conversation mode."""
        with self._lock:
            self._mode = value

    @property
    def audio_level(self) -> float:
        """Get current audio level (0.0-1.0)."""
        with self._lock:
            return self._audio_level

    @audio_level.setter
    def audio_level(self, value: float) -> None:
        """Set audio level, clamped to 0.0-1.0."""
        with self._lock:
            self._audio_level = max(0.0, min(1.0, value))
