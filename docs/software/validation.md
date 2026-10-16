# Software validation

For agents assessing software changes. Builders should follow
[setup](setup.md), [maintenance](maintenance.md) and the
[safety notice](../../hardware/SAFETY.md). Contributor commands are in
[CONTRIBUTING.md](../../CONTRIBUTING.md).

## Offline coverage

`make check` runs the repository's contributor checks, including formatting,
lint, types, software tests, hardware invariants and guide verification. See the
[CI workflow](../../.github/workflows/ci.yml) for supported Python versions and
installed-package checks. Run checks against the candidate being delivered;
historical test counts do not certify a later revision.

Tests replace native/cloud boundaries where needed. They do not move hardware,
record ambient audio or make paid API calls. Important coverage includes:

| Supported behavior | Current verification destination |
| --- | --- |
| Button activation, greeting, concurrent Live connect, microphone resumes after greeting | `test_openai_runtime.py`, `test_application.py::test_real_application_session_media_audio_chain` |
| Context, corrections, inactivity/session ceilings, stale audio/results | `test_openai_runtime.py`, `test_openai_activities.py`, `test_openai_live.py` |
| Scanner loops and ducks while microphone and speech continue | `test_audio_controller.py::test_scanner_and_stale_stop_preserve_capture_and_speech`, `test_background_sound.py`, `test_media_coordinator.py`, application chain above |
| Immediate mute, drain/flush, blocked drivers, cancellation and release failure | `test_audio_controller.py`, `test_capture_handoff.py`, `test_application.py` process-deadline/cleanup cases |
| Sleep/dance announcements precede action; uncertain actions are not replayed | `test_openai_activities.py`, `test_openai_responses.py`, `test_openai_tool_executor.py` |
| Dance song, beats, completion and button return greeting | `test_hardware_tools.py::test_real_dance_uses_every_second_beat_and_clears_ambient_hold`, `test_hardware_controller.py`, `test_openai_activities.py` |
| Timer/doorbell preemption, chime, announcement, acknowledgement and outage dismissal | `test_openai_activities.py`, `test_openai_alert_ack.py`, `test_hardware_controller.py`, `test_runtime_resources.py` |
| Six animations, head direction/speed, ambient holds, LEDs and speech movement | `test_hardware_tools.py`, `test_hardware_presentation.py`, `test_hardware_controller.py` |
| Ten logical tools, schemas, deduplication, bounded execution and context ownership | `test_tool_registry.py`, `test_openai_responses.py`, `test_openai_tool_executor.py` |
| Content lookup, Roku, Ring setup, timers and overdue policy | `test_tool_handlers.py`, `test_roku_network_bounds.py`, `test_integration_configuration.py`, `test_runtime_resources.py` |
| USB selection, gain, resampling, coloration and resources | `test_audio_device_selection.py`, `test_audio_controller.py`, `test_pcm_resampler.py`, `test_openai_voice_effects.py`, `test_runtime_resources.py` |
| Custom SSH host/user, provision/update repair, settings preservation, service controls and foreground restoration | `test_deployment.py`, `test_deploy_config.py`, `test_application_config.py`, `test_runtime_environment.py` |
| Audio/microphone/servo/LED diagnostics and external calibration state | `test_deployment.py`, `test_runtime_environment.py`, `test_hardware_tools.py` |
| Beat analysis, model comparison, sound generators and license/assets | [Beat helper instructions](beat-analysis.md), `test_openai_model_evaluation.py`, deployment/resource and package checks |
| Privacy, settings precedence, literal env parsing and hardware-free imports | `test_log_privacy.py`, `test_application_config.py`, `test_runtime_environment.py`, `test_ai_mode_isolation.py`, `test_openai_orchestrator.py` |

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
These tests do not establish physical pulse timing, loaded operation or assembly
clearance; nominal datasheet travel does not establish mechanical stop margin.

## Audio contract

Capture converts physical 48 kHz audio directly to the 24 kHz speech stream.
Offline coverage checks packet continuity, alias rejection, duration, converter
flushes, cancellation, gain preservation, generation fencing and playback drain.
See the [audio pipeline](audio-pipeline-cleanup.md) and
[runtime architecture](architecture.md). These tests do not prove acoustic echo,
USB/ALSA timing or clipping performance on the assembled device.

<a id="physical-qualification"></a>

## Device experience and limits

The author reports a complete prototype build, testing and guide review; see
[build experience and limitations](../../hardware/SAFETY.md#build-experience-and-limitations).
This is not comprehensive testing or certification.

Historical evidence:

- Earlier development tests used a Pi 3B+. The [dependency constraints](../../requirements/pi-py313.txt)
  record a hardware-dependency installation on that board; this is historical
  evidence, not an alternative board recommendation for the current build.
- September–October 2026 conversations included successful spoken follow-ups,
  but also clipping and an intermittent missed follow-up. A successful diagnostic
  did not establish a fix or prove clipping caused the missed response.
- An October 13 installed-application test exercised head commands, search,
  overlapping follow-up, sleep, dance and button-equivalent cancellation, with
  clean shutdown. It used synthetic microphone input; it did not measure quiet
  human speech or independently confirm physical head position. An earlier run
  timed out during search and shut down cleanly.
- That final run recorded one capture overflow. Later short comparisons did not
  reproduce it; neither its cause nor a fix was established.

These observations concern earlier software/configurations, not a test of the
current revision. Their applicability to the current assembly is unestablished.
Offline tests do not resolve acoustic questions or prove LED output, servo travel
or loaded mechanics.

## Optional device evaluation

For a contributor investigating behavior or extending configuration support:

- Exercise greeting, search, follow-up, interruption, button stops, dance, alerts,
  timers, sleep and API/network recovery. Check voice consistency, echo, tool
  actions and session closure for duplicate or stale actions.
- Check fresh Imager-to-Make installation, repeat provisioning, reboot and
  update-failure/repair on the chosen Pi/audio combination.
- The proposed measurement protocol is at least 30 button stops across activities
  and a 60-minute mixed-activity run. Targets: p95 button-to-audible-stop ≤250 ms
  and spoken interruption-to-old-speech-stop ≤500 ms, at least 30 trials per
  scenario, and no echo-triggered tool actions. These are optional targets, not
  achieved results, builder requirements or promised future work. No latency or
  CPU/memory improvement is claimed.

Physical diagnostics, motion and real API calls require explicit authorization.
Check quiet human speech and speaker bleed before accepting gain settings; change
one variable at a time. Record exact software/dependency versions, board, OS, audio devices, gains and
microphone/speaker placement privately. Publish useful conclusions, not recordings
or transcripts; keep those out of routine logs.

## Operational validation

After an authorized provision/update, use `make pi-status` and `make pi-logs` to
check readiness, restart counts, capture/playback errors and available memory
under representative use. Investigate failed media release, repeated restarts,
OOM or sustained swap dependence. Repair the reported cause and rerun the normal
procedure. For publication, follow the [release checklist](../release/checklist.md).
