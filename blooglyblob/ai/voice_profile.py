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
        if heading in {"Your Story", "Your Personality", "Your Capabilities"}:
            selected.append(body.strip())
    selected += [
        speech_instructions(),
        "Keep each response to one or two short sentences and one idea. Listen and let the user interrupt naturally.",
        (
            "Backchannel policy: Keep listening acknowledgements brief. Avoid filler "
            "during action requests.\n"
            "\n"
            "Interruption policy: Stop speaking when the user interrupts and listen to "
            "their correction.\n"
            "\n"
            "Delegation policy:\n"
            "Backend tools:\n"
            "- Sleep and goodbye: play the robot's farewell and put it to sleep.\n"
            "- Dance: play the robot's introduction and start its built-in dance.\n"
            "- Physical actions, timers, media, and device controls.\n"
            "- Galactic Scanner: look up current information on the Internet.\n"
            "\n"
            "Delegate to the backend when:\n"
            "- The user asks the robot to sleep, end the conversation, or dance.\n"
            "- The user requests another backend capability or current information.\n"
            "- The user changes or cancels requested work.\n"
            "\n"
            "Do not delegate to the backend when:\n"
            "- You can answer from the conversation or a still-current result.\n"
            "- The user is only discussing an action rather than requesting it.\n"
            "- You need a brief clarification to understand the request.\n"
            "\n"
            "Delegate before giving an answer that depends on backend work. The backend "
            "supplies the complete spoken farewell or dance introduction; let it provide "
            "that response. For other tasks, explain the verified result naturally. Never "
            "claim success before a verified result. Keep tool identifiers internal.\n"
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
