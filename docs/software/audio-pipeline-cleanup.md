# Audio pipeline

The application uses mono PCM16 at 24 kHz for speech and the configured OpenAI
Live connection. Physical 48 kHz microphone capture converts directly to 24 kHz;
the cloud transport does not resample it. See the
[runtime architecture](architecture.md) for ownership and session behavior.

## Conversion and playback

One streaming PCM converter serves capture, speech playback, scanner preparation
and converted WAV playback. It preserves filter state across packets, exact
finite-stream duration and end-of-stream flushes. Stopping capture discards
buffered input from the retired generation.

The 16 kHz alert/scanner assets convert at the 48 kHz speaker boundary. Dance uses
its native 44.1 kHz stereo rate. Optional voice coloration preserves bit-exact
playback when disabled, generation isolation and the finished-generation guard.
Actual driver drain/release futures and talking-level callbacks remain distinct
from packet delivery; cancellation must not release audio ownership prematurely.

## Verification and limits

Offline tests cover capture and transport contracts, anti-alias filtering,
finite-stream sample counts/tails, split-packet equivalence, gain preservation,
file completion/cancellation, voice coloration, scanner ducking and lifecycle
failures. See [software validation](validation.md) for test destinations and
remaining physical qualification.

Device acceptance requires listening through conversation, search and follow-up
questions, interruption, dance and alerts. Check pitch/duration and scanner
ducking, and inspect capture/output overflow, playback failure, unexpected idle
transitions and exit 73. Investigate ownership and input delivery rather than
changing gain or increasing queues to hide faults. Offline checks cannot
establish USB/ALSA timing, acoustic echo or clipping performance on the Pi.
