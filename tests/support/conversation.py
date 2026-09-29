from typing import ClassVar
from unittest.mock import AsyncMock, Mock
from blooglyblob.conversation import ConversationSession


class Live:
    instances: ClassVar[list] = []

    def __init__(self, **kwargs):
        self.callbacks = kwargs
        self.close = AsyncMock()
        self.input_audio = AsyncMock()
        self.append_result = AsyncMock()
        self.discard_output = Mock()
        self.instances.append(self)

    async def start(self, greeting=""):
        pass


class Audio:
    ownership_uncertain = False

    def __init__(self):
        from blooglyblob.audio.presentation import OutputPresentation

        self.presentation = OutputPresentation()
        self.trace = []
        self.mute = Mock()
        self.begin = AsyncMock(side_effect=self._begin)
        self.audio = AsyncMock(side_effect=self._audio)
        self.drain = AsyncMock(side_effect=self._drain)
        self.flush = AsyncMock(side_effect=self._flush)
        self.release = AsyncMock(side_effect=self._release)
        self.start_background = AsyncMock(side_effect=self._start_background)
        self.stop_background = AsyncMock(side_effect=self._stop_background)

    async def _begin(self, generation):
        self.trace.append({"type": "begin", "generation": generation})

    async def _audio(self, generation, pcm):
        self.trace.append({"type": "audio", "generation": generation, "pcm": pcm})

    async def _drain(self, generation):
        self.trace.append({"type": "drain", "generation": generation})

    async def _flush(self, generation):
        self.trace.append({"type": "flush", "generation": generation})

    async def _release(self):
        self.trace.append({"type": "release"})

    async def _start_background(self, activity, generation):
        self.trace.append(
            {
                "type": "start_background",
                "activity_id": activity,
                "generation": generation,
            }
        )

    async def _stop_background(self, activity):
        self.trace.append({"type": "stop_background", "activity_id": activity})


class Hardware:
    ownership_uncertain = False

    def __init__(self, audio):
        from blooglyblob.hardware.lighting import LightingState

        self.lighting = LightingState(audio.presentation)
        self.light = self.lighting.set_mode
        self.pending_light = self.lighting.pending
        self.trace = audio.trace
        self.mute_media = Mock()
        self.execute = AsyncMock(return_value="Going to sleep")
        self.stop_media = AsyncMock(side_effect=self._stop_media)
        self.chime = AsyncMock(side_effect=self._chime)
        self.present = Mock(
            side_effect=lambda state: self.trace.append(
                {"type": "present", "state": state}
            )
        )

    async def _stop_media(self):
        self.trace.append({"type": "stop_media"})

    async def _chime(self, activity):
        self.trace.append({"type": "chime", "activity_id": activity})


def session(**kwargs):
    Live.instances = []
    audio = Audio()
    hardware = Hardware(audio)
    instance = ConversationSession(
        audio=audio,
        hardware=hardware,
        api=object(),
        live_factory=Live,
        instructions="curious",
        **kwargs,
    )
    return instance, hardware, audio
