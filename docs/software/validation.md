# Software validation

Offline checks, installation checks and physical qualification establish different
things. Follow [setup](setup.md) and [maintenance](maintenance.md) for operating
procedures and [CONTRIBUTING.md](../../CONTRIBUTING.md) for contributor checks.
This page describes coverage and remaining limits, not a device-testing diary.

## Offline coverage

`make check` runs the repository's contributor checks, including formatting,
lint, types, software tests, hardware invariants and guide verification. See the
[CI workflow](../../.github/workflows/ci.yml) for supported Python versions and
installed-package checks. Run checks against the candidate being delivered;
historical test counts do not certify a later revision.

Tests replace native/cloud boundaries where needed. They do not move hardware,
record ambient audio or make paid API calls. Important coverage includes:

| Supported behavior | Current verification destination | Area |
| --- | --- | --- |
| Button activation, greeting, concurrent Live connect, microphone resumes after greeting | `test_openai_runtime.py`, `test_application.py::test_real_application_session_media_audio_chain` | Application and conversation |
| Context, corrections, inactivity/session ceilings, stale audio/results | `test_openai_runtime.py`, `test_openai_activities.py`, `test_openai_live.py` | Conversation and AI adapters |
| Scanner loops and ducks while microphone and speech continue | `test_audio_controller.py::test_scanner_and_stale_stop_preserve_capture_and_speech`, `test_background_sound.py`, `test_media_coordinator.py`, application chain above | Media and audio |
| Immediate mute, drain/flush, blocked drivers, cancellation and release failure | `test_audio_controller.py`, `test_capture_handoff.py`, `test_application.py` process-deadline/cleanup cases | Audio and application lifecycle |
| Sleep/dance announcements precede action; uncertain actions are not replayed | `test_openai_activities.py`, `test_openai_responses.py`, `test_openai_tool_executor.py` | Conversation and tool execution |
| Dance song, beats, completion and button return greeting | `test_hardware_tools.py::test_real_dance_uses_every_second_beat_and_clears_ambient_hold`, `test_hardware_controller.py`, `test_openai_activities.py` | Hardware local media and audio |
| Timer/doorbell preemption, chime, announcement, acknowledgement and outage dismissal | `test_openai_activities.py`, `test_openai_alert_ack.py`, `test_hardware_controller.py`, `test_runtime_resources.py` | Conversation, audio and integrations |
| Six animations, head direction/speed, ambient holds, LEDs and speech movement | `test_hardware_tools.py`, `test_hardware_presentation.py`, `test_hardware_controller.py` | Hardware controller and presentation |
| Ten logical tools, schemas, deduplication, bounded execution and context ownership | `test_tool_registry.py`, `test_openai_responses.py`, `test_openai_tool_executor.py` | AI tool bridge and tools |
| Content lookup, Roku, Ring setup, timers and overdue policy | `test_tool_handlers.py`, `test_roku_network_bounds.py`, `test_integration_configuration.py`, `test_runtime_resources.py` | Tools and configuration |
| USB selection, gain, resampling, coloration and resources | `test_audio_device_selection.py`, `test_audio_controller.py`, `test_pcm_resampler.py`, `test_openai_voice_effects.py`, `test_runtime_resources.py` | Audio and resource packages |
| Custom SSH host/user, provision/update repair, settings preservation, service controls and foreground restoration | `test_deployment.py`, `test_deploy_config.py`, `test_application_config.py`, `test_runtime_environment.py` | Installer and single service |
| Audio/microphone/servo/LED diagnostics and external calibration state | `test_deployment.py`, `test_runtime_environment.py`, `test_hardware_tools.py`; explicit physical qualification pending | Diagnostics and hardware modules |
| Beat analysis, model comparison, sound generators and license/assets | [Beat helper instructions](beat-analysis.md), `test_openai_model_evaluation.py`, deployment/resource and package checks | Optional scripts/resources |
| Privacy, settings precedence, literal env parsing and hardware-free imports | `test_log_privacy.py`, `test_application_config.py`, `test_runtime_environment.py`, `test_ai_mode_isolation.py`, `test_openai_orchestrator.py` | All owners and packaging |

## Servo fitting contract

Startup and `make pi-servo-fit` share immutable positions: left GPIO12 at 2000 µs,
right GPIO13 at 1000 µs and head GPIO16 at 1500 µs. Every axis uses 1000–2000 µs
at 50 Hz. Outputs open without a pulse; startup sets rest directly without a
sweep through center. The fit command requires the installation lock and a
confirmed service stop, holds outputs until STOP, releases without recentering
on STOP/EOF/interruption/failure, and leaves the application stopped.
Unconfirmed release reports status 73.

Saved legacy calibration files are preserved but ignored. Robots whose horns
were fitted at different positions must be refitted before operation. Regression
coverage checks fixed bounds, directions, cleanup, stop/lock refusal, ignored
calibration and agreement between instructions and configured outputs.
Physical pulse timing, loaded operation and assembly clearance require separate
qualification; nominal datasheet travel does not establish mechanical stop margin.

## Audio contract

Capture converts physical 48 kHz audio directly to the 24 kHz speech stream.
Offline coverage checks packet continuity, alias rejection, duration, converter
flushes, cancellation, gain preservation, generation fencing and playback drain.
See the [audio pipeline](audio-pipeline-cleanup.md) and
[runtime architecture](architecture.md). These tests do not prove acoustic echo,
USB/ALSA timing or clipping performance on the assembled device.

## Physical qualification

Full normal-application and acoustic qualification remain open. Maintainer tests
should exercise greeting, search, follow-up questions, interruption, button stops,
dance, alerts, timers, sleep, and API/network recovery with the current hardware.
Check voice consistency, speaker echo, tool actions and session closure without
duplicate or stale actions. Record exact software/dependency versions, board,
OS image, audio devices, gain settings and microphone/speaker placement privately.
Publish only the resulting useful limitations or verified supported behavior.

The existing proposed qualification protocol includes at least 30 button stops
across activities and a 60-minute mixed-activity run. Proposed measurement targets
are p95 button-to-audible-stop ≤250 ms and spoken interruption-to-old-speech-stop
≤500 ms, with at least 30 trials per scenario and no echo-triggered tool actions.
These are maintainer test targets, not achieved results or assembly steps imposed
on every builder. No latency or CPU/memory improvement is claimed.

A complete fresh Imager-to-Make installation, repeat provisioning, reboot,
update-failure/repair and representative use must be qualified for the reference
Pi and replacement audio. Software-only startup does not qualify speakers,
microphone placement, LED output, servo travel or loaded mechanics. Capture
clipping and missed follow-up behavior need evaluation in the complete assembly;
passing offline tests does not establish that these acoustic issues are resolved.

Physical diagnostics, motion and real API calls require explicit authorization.
For an authorized test, verify quiet human speech and speaker bleed before
accepting gain settings; change one variable at a time. Do not keep recordings
or transcript text in routine logs.

## Operational validation

After an authorized provision/update, use `make pi-status` and `make pi-logs` to
check readiness, restart counts, capture/playback errors and available memory
under representative use. Investigate failed media release, repeated restarts,
OOM or sustained swap dependence. Repair the reported cause and rerun the normal
procedure. Repository cleanup does not clear the
[release qualification checks](../release/checklist.md).
