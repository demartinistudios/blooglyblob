from blooglyblob.ai import voice_profile


def test_profile_keeps_character_and_delivery_without_live_tool_procedures():
    live = voice_profile.live_instructions()
    speech = voice_profile.speech_instructions()
    backend = voice_profile.backend_instructions()
    assert "Blue-glee-blob" in live and "Meep" in live
    assert "curious" in live.lower() and "curious" in speech.lower()
    assert "delegate" in live.lower() and "verified" in live.lower()
    assert "setTimer" not in live and "findTimers" not in live
    assert "setTimer" in backend
    assert "[excited]" not in live + speech + backend
    assert voice_profile.default_voice() == "ballad"
    assert voice_profile.default_speech_voice() == voice_profile.default_voice()
    assert "British English" in live and "British English" in speech
    assert voice_profile.default_greeting().startswith("Hey! I'm Blue-glee-blob")


def test_live_greeting_is_explicit_optional_start_instruction():
    assert "CUSTOM HELLO" in voice_profile.live_instructions("CUSTOM HELLO")
