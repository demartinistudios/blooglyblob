"""The four finite announcements shared by startup and conversation ownership."""

from blooglyblob.ai.voice_profile import default_greeting

GREETING_SPEED = 1.25
SLEEP_FAREWELL = "Goodnight! Catch you on the next orbit."
DANCE_INTRODUCTION = "Let's dance! Time to party!"
DANCE_RETURN_GREETING = "That was fun! What's next?"
ANNOUNCEMENT_SLOTS = frozenset({"greeting", "sleep", "dance", "dance_return"})


def fixed_announcements(greeting: str | None = None) -> dict[str, tuple[str, float]]:
    return {
        "greeting": (
            default_greeting() if greeting is None else greeting,
            GREETING_SPEED,
        ),
        "sleep": (SLEEP_FAREWELL, 1.0),
        "dance": (DANCE_INTRODUCTION, 1.0),
        "dance_return": (DANCE_RETURN_GREETING, GREETING_SPEED),
    }
