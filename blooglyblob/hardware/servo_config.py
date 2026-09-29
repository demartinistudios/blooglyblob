"""Fixed FS90MG-CL operating positions; independent of local calibration files.

The supported window remains 1000–2000 µs at 50 Hz. Normalized -1/+1
select that window, not the servo's full nominal mechanical travel.
"""

from dataclasses import dataclass

MIN_PULSE_WIDTH = 0.001
MAX_PULSE_WIDTH = 0.002
FRAME_WIDTH = 0.02


@dataclass(frozen=True)
class ServoProfile:
    """Ordered semantic endpoints (arms down/up, head left/right) and rest."""

    start: float = -1.0
    end: float = 1.0
    rest: float = 0.0

    def clamp(self, value: float) -> float:
        return max(-1.0, min(1.0, value))

    def at_percent(self, percent: float) -> float:
        percent = max(0.0, min(100.0, percent))
        return self.start + (self.end - self.start) * percent / 100.0

    def percent_at(self, position: float) -> float:
        return max(0.0, min(100.0, (position - self.start) / (self.end - self.start) * 100.0))


LEFT_ARM = ServoProfile(start=1.0, end=-1.0, rest=1.0)
RIGHT_ARM = ServoProfile(start=-1.0, end=1.0, rest=-1.0)
HEAD = ServoProfile(start=1.0, end=-1.0, rest=0.0)
