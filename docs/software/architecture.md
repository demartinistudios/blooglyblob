# Application architecture

Blooglyblob runs as one Python application on the Raspberry Pi, started with
`python -m blooglyblob` and managed by `blooglyblob.service`. The button starts
a conversation. OpenAI supplies cloud AI; there is no local language model.
Follow [setup](setup.md) and [maintenance](maintenance.md)
for installation and operation.

## Internal responsibilities

| Module | Owns |
| --- | --- |
| `blooglyblob/application.py` | Startup, readiness, signals, shared API client, integrations, and shutdown |
| `blooglyblob/conversation.py` | Conversation, idle, dance, and alert transitions; activity generations and tool context |
| `blooglyblob/media.py` | Direct speech, scanner, drain, and media-release coordination |
| `blooglyblob/audio/` | Microphone capture, bounded PCM handoff, one speaker owner, mixing and resampling |
| `blooglyblob/hardware/` | Button, LEDs, servos, presentation, local dance/chime workers and diagnostics |
| `blooglyblob/ai/` | OpenAI Live, Responses, Speech, validation, persona and voice resources |
| `blooglyblob/tools/` | Tool schemas/execution, timers, Ring, Roku, and content lookup |

These modules call one another directly. There is no local brain/device server,
network protocol, device registration, or reconnect loop. OpenAI connections
still use the internet. The existing `pigpiod` daemon remains a GPIO prerequisite.
The application retains the root permissions required by the current LED/GPIO drivers.

## Settings and voice

Select one runtime file with `BLOOGLYBLOB_ENV_FILE`; the installed service uses
`/etc/blooglyblob/app.env`. Explicit process values take precedence. Files are
read literally without shell execution or variable interpolation. The root
`.env` contains host-side deployment settings and is not loaded by the application.

Bring your own `OPENAI_API_KEY`. Live, Responses, and Speech requests are billed
to your account. Defaults remain `gpt-live-1`, `gpt-5.6-terra`, and
`gpt-4o-mini-tts`, respectively; your account must support the configured models.
The [runtime template](../../config/app.env.example) lists model, audio and
integration settings. `OPENAI_INACTIVITY_SECONDS` defaults to 20 and
`OPENAI_SESSION_MAX_SECONDS` to 600. These bound one conversation, not total
spending. No provider fallback exists.

`blooglyblob/ai/persona.json` defines the character.
`blooglyblob/ai/voice_profile.json` supplies Ballad, delivery instructions, pace,
expression and pronunciation. `OPENAI_VOICE` overrides the shared voice;
`OPENAI_SPEECH_VOICE` can override finite announcements separately. The APIs use
different synthesis paths, so matching settings still need a listen on the Pi.

Optional ring modulation uses the profile's `output_effect` settings. It is
currently disabled (`mix: 0.0`), which preserves PCM unchanged. `mix` ranges
from 0.0 to 1.0; integer `carrier_hz` ranges from 1 to 400. It preserves sample
count, adds no lookahead or buffered tail, and never increases individual sample
magnitude. There is no automatic loudness processing or replacement DSP.
Restart the application after a profile change. Deploy accepted profile edits
with `make pi-update`; installed source edits are replaced by the next update.
Audio tuning and the existing clipping/follow-up investigation remain separate
from this architecture change.

## Audio formats

Internal speech is mono, signed 16-bit PCM at 24 kHz. The microphone captures
48 kHz and one continuous SoXR converter produces 24 kHz directly. Live receives
those samples unchanged, framed and paced for transport. Incoming Live/Speech
PCM stays at 24 kHz through optional coloration; the speaker writer converts it
once to the device's 48 kHz rate.

The same converter prepares the 16 kHz scanner recording once at startup and
converts the 16 kHz alert during file playback. Dance plays at its native
44.1 kHz stereo rate. Converted streams preserve filter state between packets;
normal completion flushes the short filter tail, while cancellation discards it.
There is no intermediate 16 kHz microphone format or codec transcoding. Current
device selection and microphone gain remain unchanged.

## Conversations and activities

Greeting preparation runs after local readiness and can make a billable Speech
request even before the first button press. A prepared greeting is reused;
otherwise Speech streams it on demand. Its existing voice and speed are retained.
Live connects concurrently. Microphone input is withheld until the greeting
physically drains, to avoid forwarding that locally generated speech as input.
Normal duplex capture resumes immediately afterward. A bounded queue covers any
remaining Live connection setup; stopping discards that session's input.

The scanner loops quietly through the conversation's speaker writer during web
search. Speech lowers its volume; microphone capture and incoming speech keep
flowing. Completion, failure or cancellation removes the effect. Background-only
samples do not drive talking gestures. Dance and
alert recordings use sequential speaker ownership.

For clear standalone sleep/dance requests, the conversation briefly withholds
Live playback while Responses selects the action. This narrow hint does not
authorize an action. It expires after six seconds and releases on a nonterminal
result, failure, or new speech. Negation and questions about those activities do
not trigger it. Tool arguments still pass schema validation; uncertain actions
are not automatically replayed under a new call ID.

Sleep/dance announcements must physically drain before the action starts.
Matching dance completion returns to conversation with the existing greeting.
Timers and doorbell alerts retain their preemption, acknowledgement, dismissal,
and time-limit behavior. An alert during an active alert is dropped; overdue
saved timers are discarded at startup rather than replayed.

Meaningful conversation activity resets inactivity; silent PCM does not. Owned
tool work suspends inactivity shutdown while the overall session ceiling still
applies. Optional integrations retain their existing roles and configuration.

<a id="audio-lifecycle-invariants"></a>

## Completion and failure rules

- The conversation owns activity and generation decisions. Presentation never
  determines whether microphone input is accepted.
- Audio owns every speaker stream. Queue acceptance, effect removal, physical
  drain, and full driver release are distinct completions.
- The button mutes locally before waiting for the event loop or cloud. Stale
  audio and action results cannot reactivate a retired generation.
- Native workers must finish before their resources are released or reused.
  Cancellation of an await does not mean its thread stopped.
- Routine provider failure with confirmed closure returns to idle. Missing
  final usage alone is a warning when transport closure is confirmed.
- Unconfirmed ownership mutes and stops the application with exit status 73.
  The service does not automatically restart that status; inspect logs and
  restart explicitly after resolving the cause. Startup and shutdown have
  finite deadlines, including foreground execution and Python thread teardown.

Talking gestures and body lights follow actual speaker level while conversation
remains listening. Silence, drain, flush, mute and failures clear that level.
Pose holds and animation locks remain authoritative; sleep, dance and alert
presentation retain their existing behavior. Eyes are controlled separately.
The supported 16-pixel data chain uses body indices 0–5, eyes 6–7, and mouth
8–15. The mouth is explicitly dark during normal operation; this profile update
does not add a mouth animation. The [LED diagnostic](maintenance.md#supported-led-chain)
exercises every pixel without changing the F2-protected lighting supply.

## Verification

`make pi-status` and `make pi-logs` describe the single application service.
Readiness means required local initialization and controls completed; it does
not open a conversation or prove cloud access, acoustic quality, or movement.

`make dev-check` runs formatting, lint, type checks, and hardware-free tests without API
credentials. The [validation coverage](validation.md) separates offline checks
from physical qualification, including capture clipping and follow-up behavior
that still need evaluation in the complete assembly.
