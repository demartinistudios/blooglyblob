"""Thread-safe conversation mode for ambient motion admission."""

import threading
from enum import Enum


class ConversationMode(Enum):
    """Current conversation activity."""

    IDLE = "idle"  # Not in conversation - calm ambient pattern
    LISTENING = "listening"  # Waiting for user input - cyan/blue pulse
    PROCESSING = "processing"  # STT/LLM processing - thinking
    SPEAKING = "speaking"  # Agent responding - orange/yellow, audio-reactive
    DANCING = "dancing"  # Dance mode active
    ALERT = "alert"  # Timer firing - fast red pulse, urgent


class ConversationState:
    """Thread-safe conversation mode shared with ambient motion.

    Attributes:
        mode: Current conversation mode (IDLE, LISTENING, SPEAKING)
    """

    def __init__(self):
        """Initialize with IDLE state."""
        self._lock = threading.Lock()
        self._mode = ConversationMode.IDLE

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
