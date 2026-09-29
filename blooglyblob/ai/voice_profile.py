"""One character source, with shared editable speech delivery."""

import json
import re
from pathlib import Path

_ROOT = Path(__file__).parent


def _persona():
    return json.loads((_ROOT / "persona.json").read_text())


def _profile():
    return json.loads((_ROOT / "voice_profile.json").read_text())


def default_voice() -> str:
    return _profile()["voice"]


def default_speech_voice() -> str:
    profile = _profile()
    return profile.get("speech_voice", profile["voice"])


def default_greeting() -> str:
    return _persona()["first_message"]


def output_effect_factory():
    """Create independent effect state for each Live or finite speech stream."""
    from functools import partial

    from blooglyblob.audio.voice_effects import RingModulator

    profile = _profile()
    return partial(RingModulator, **(profile.get("output_effect") or {}))


def speech_instructions() -> str:
    profile = _profile()
    return "\n".join(
        profile[key] for key in ("tone", "pace", "expressiveness", "pronunciation")
    )


def live_instructions(greeting: str = "") -> str:
    persona = _persona()["persona_prompt"]
    # Share the original story/personality; detailed action procedures belong to
    # the brain's task backend, never the conversational Live frontend.
    sections = re.split(r"(?m)^## ", persona)
    selected = [sections[0].strip()]
    for section in sections[1:]:
        heading, _, body = section.partition("\n")
        if heading in {"Your Story", "Your Personality", "How You Use Slang"}:
            selected.append(body.strip())
    selected += [
        speech_instructions(),
        "Keep each response to one or two short sentences and one idea. Listen and let the user interrupt naturally.",
        (
            "Delegate physical actions, sleep/goodbye actions, timers, searches, media, and corrections or cancellations to active work to the brain backend. "
            "Delegation requests are work requests, not proof of completion. Never claim an action succeeded until the backend provides a verified result. "
            "Keep tool identifiers internal. Use the conversation as context for delegated work."
        ),
        (
            "For a clear request to go to sleep, end the conversation, or start dancing, "
            "delegate immediately and remain silent while the backend takes over. "
            "The application plays exactly one goodnight or dance introduction before the action. "
            "Do not add your own acknowledgement, farewell, offer to help, status update, or follow-up question. "
            "Use actual silence: no 'mm', 'hmm', humming, or other filler sounds. "
            "In particular, do not say 'let me check', 'let me help', or 'I'll see about that'. "
            "Discussing sleep or dancing is not itself an action request. Respect negation and corrections; "
            "ask a short clarification only when the user's intended action is genuinely ambiguous."
        ),
    ]
    if greeting:
        selected.append("Begin with this brief greeting: " + greeting)
    return "\n\n".join(selected)


def backend_instructions() -> str:
    return (
        _persona()["persona_prompt"]
        + "\n\n"
        + speech_instructions()
        + (
            "\nOnly report actions as successful after tool results verify completion. "
            "Keep spoken wording natural; never include literal emotion markers."
        )
    )
