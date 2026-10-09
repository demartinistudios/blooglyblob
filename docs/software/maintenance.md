# Maintain the Pi software

`make pi-provision` establishes or repairs required system dependencies, the
Python environment, the application, and its service. It is safe to rerun and
preserves credentials, Wi-Fi, user settings, existing device files, and timer state. It
installs required packages without performing a blanket OS upgrade.

`make pi-update` updates application code and Python dependencies only. It
checks prerequisites and validates configuration before stopping the application.
If system dependencies need changes, run provisioning first. The application is
installed from one source snapshot. Only payload files are replaced; existing
custom state and media paths are preserved.

An update stops the application, replaces its code, restarts it, and waits for
systemd readiness. Required configuration, resources, audio-device selection and
button setup must succeed before the service reports ready. This does not start
a conversation or prove cloud access, acoustic quality or mechanical movement.
After readiness, background greeting preparation can make a billable Speech
request; starting the service is therefore not an offline-only operation.
If it fails after stopping, the robot may remain unavailable.
Inspect the reported step and logs, fix the cause, and rerun. There is **no
automatic rollback**, retained previous installation, or rollback command.
Manually installing an older version requires compatibility; it does not undo
system-package or data changes. Repeatable installation is not reversible
installation.

## Commands

| Command | Purpose |
| --- | --- |
| `make pi-check` | Read-only connection, remote identity, and OS/architecture check |
| `make pi-provision` | Complete first installation or dependency repair |
| `make pi-update` | Application update |
| `make pi-status` | Status of the application service |
| `make pi-logs` | Recent journal output |
| `make pi-start`, `pi-stop`, `pi-restart` | Control the application service |
| `make pi-ssh` | Open SSH to the configured target |
| `make pi-run` | Foreground application; restore its prior active service after exit, except ownership-uncertain status 73 |
| `make pi-servo-fit` | Hold all three assembly fit positions until STOP; release pulses and leave the application stopped |
| `make pi-check-audio` | Enumerate audio devices without opening streams |
| `make pi-test-audio`, `pi-test-mic` | Play a test tone, or beep, record five seconds of speech and play it back |
| `make pi-test-neopixels` | Exercise all 16 LEDs |

Only one provisioning/update/interactive diagnostic operation may own the
installation lock. Never remove another running operation's lock to force an
update. No command kills all Python processes on the machine.

### LED driver compatibility

Provisioning and updates automatically install a pinned source build of
`rpi-ws281x 5.0.0+bgb.1`. It applies the upstream
[Pi 3A+ revision 1.1 support](https://github.com/jgarff/rpi_ws281x/commit/09f4ef2b12b448ff1bd7d461b7b557139c8f2109)
to the hash-verified 5.0.0 source archive. Existing board entries, including
3A+ revision 1.0, remain unchanged. No board-specific builder command is needed.

The installer reuses that build on subsequent runs and checks board recognition
without opening GPIO before starting the application. Download, build or
recognition failure stops installation; fix the reported cause and rerun the
same command. The ordinary 5.0.0 constraint accepts this local build version.
Do not replace it with the unpatched PyPI package. Remove the backport after a
published Python release containing the correction has been qualified.

## Supported LED chain

The application supports one 16-pixel GRB NeoPixel **data** chain on GPIO18:

| Indices | Physical location | Normal application behavior |
| --- | --- | --- |
| 0–5 | Six body pebbles | Slow mood colors for the current state; asleep, a dim slow rainbow |
| 6–7 | Two separate eye pixels | Off while asleep; on and blinking while awake |
| 8–15 | Eight-pixel mouth | Off while asleep or silent; follows the speech level while talking and the music while dancing |

While the cloud service is unreachable, the body shows a slow, dim amber glow with the
eyes and mouth off. The robot stays inactive: button presses and alerts do not
start, and nothing is queued. It returns to normal idle when connectivity
recovers, without replaying an interrupted conversation; press the button again.

This data ordering does not change the power wiring. Retain the F2-protected
lighting supply defined by the hardware wiring guide; power and data run in one
chain through the body lights and eyes to the mouth. The brightness setting
remains 128/255.
This software profile does not establish electrical or thermal qualification.

`make pi-test-neopixels` first lights one pixel at a time in ascending order,
printing its index and zone, then runs the existing solid-color and animation
tests across all sixteen pixels. All pixels clear on exit. In ordinary use the
mouth lights only while the robot talks or dances. See commissioning
limits below before running diagnostics on a partially assembled build.

## Commissioning limits

Provisioning, updating, starting or rebooting starts the application and can move
servos. There is no motion-disabled installation mode. Follow the build guide's
staged power checks with the head and arms off their shafts before installing or
updating an uncommissioned mechanism.

`make pi-servo-fit` takes the installation lock, stops the application and confirms
its stopped state before opening any outputs. It holds all three servos at once:
robot-left GPIO12 at 2000 µs, robot-right GPIO13 at 1000 µs, and head GPIO16 at
1500 µs. All use 50 Hz. Type `STOP` and press Enter to stop pulses. EOF or an
interrupt also releases outputs without recentering. The application stays
stopped even if it was running beforehand. Shutdown failure reports status 73;
if that occurs, switch off the supply and resolve the fault.

Seat the head shelf and arms while the servos hold, then type `STOP`, shut down,
unplug and drive the center screws while supporting each part. Unpowered shafts
are not position-locked; if a part turns, repeat the fitting. Follow the
[servo fit reference](../../hardware/build-guide/src/downloads/servo-fit-reference.md)
for horn fitting and the guide's first-movement check. Every replacement servo
needs that fitting and clearance check.

Normal startup opens outputs without a pulse, then commands that same fit
position directly once, without a software sweep through center. Runtime movement
stays within **1000–2000 µs** on every axis. Fixed arm percentages map down to
forward raise in opposite pulse directions. Exact angles depend on the servo,
horn indexing and assembly. This operating window does not certify clearance;
wider travel needs separately observed qualification on the new assembly.

The old `pi-calibrate-servos` and `pi-test-servos` commands are retired.
`SERVO_CALIBRATION_FILE` and saved calibration JSON no longer control movement;
existing device files are preserved without being read or rewritten by the servo
controller. Before updating a previously calibrated robot, keep the head and
arms off their shafts and refit them for the fixed positions before operation.

Other diagnostics stop the application and restore it afterward if it was active
on entry. Run `make pi-stop` first when it must stay stopped. A LED or audio test
can therefore be followed by servo motion from application startup. Starting or
rebooting later can also initiate motion; STOP is not a latched power cutoff.

## Configuration and state

| Location | Contents |
| --- | --- |
| `/opt/blooglyblob/app` | Replaceable application and bundled resources |
| `/opt/blooglyblob/venv` | Application Python environment |
| `/etc/blooglyblob/app.env` | OpenAI key, audio settings and optional integration credentials |
| `/var/lib/blooglyblob/brain` | Persistent timers |
| `/var/lib/blooglyblob/device` | Preserved legacy device files; calibration is unused |

Explicit service environment values take precedence over the selected config
file. Files are parsed as data, without shell execution or implicit searches
through parent directories. Ordinary updates do not copy local credentials over
existing Pi configuration. Edit the remote configuration intentionally over SSH,
then run `make pi-restart`.

The application runs as root for the existing GPIO/LED drivers. Its internal AI,
audio and hardware modules share that process and privilege level.

Optional Ring/Roku setup helpers accept `BLOOGLYBLOB_ENV_FILE` and preserve other
settings. Their local default is `config/app.env`. Install
`requirements-integrations.txt` on the computer running the Ring helper. After
first installation, apply intended changes to the remote `app.env` deliberately;
rerunning provision or update does not overwrite it.

The Ring doorbell alert is experimental. Ring publishes no public API for it:
setup signs in with the community `ring-doorbell` library, and the application
then polls Ring's private app interface, which can change without notice. The
application does not refresh the saved login; if alerts stop, rerun
`make dev-setup-ring` and update the Pi's `RING_TOKEN`.

### First installation and repeated updates

Provisioning validates and privately installs the selected `app.env` when the Pi
does not already have one. Once installed, the remote file is authoritative:
updates and repeated provisioning validate it and preserve its exact contents.
Existing systemd drop-ins stay in place. The installer does not merge old
configuration files, reset saved state, or make recovery copies on each update.

The development Pi's conversion from two applications is complete. The installer
now supports fresh installations and updates of the single application. Existing
timer location remains in use and existing device files are preserved; their directory names
do not represent separate applications. Private recovery files from the completed
conversion may remain on that Pi, but are not part of installation or runtime.

### Failure and device ownership

Ordinary cloud errors with confirmed cleanup return the application to idle.
If a native worker or cloud transport cannot be confirmed closed, the application
mutes and exits with status 73. Systemd does not automatically restart that status.
Inspect `make pi-logs`, resolve the failure, then explicitly restart.

Interactive diagnostics hold the installation lock and stop the service first.
On interruption, the helper terminates and waits for the diagnostic process,
using a bounded kill-and-wait fallback. It restores the previous active service
only after confirming the process exited. Unconfirmed release leaves it stopped.
Foreground application exit status 73 also leaves it stopped, including when
that status is observed during interrupted cleanup. Process exit alone does not
override the requirement to inspect an ownership failure before restarting.

Streaming availability currently prefers US watch-provider results. When those
are absent, it uses the first region returned by TMDB. This is not a reliable
availability check for other countries; there is no region setting yet.

## Log privacy

Routine tool, timer, Roku, and Ring logs record operations, counts, outcomes,
retry timing, HTTP status codes, and error classes. They omit tool arguments,
timer labels, searches, content IDs, and Ring device names/IDs. Tool results and
saved timers still contain the information needed to perform the requested work.

Review logs before sharing them: other diagnostics can include paths, configured
device identifiers, network information, or third-party output. This cleanup
does not sanitize existing journal entries. Interactive
Roku discovery intentionally displays device names and addresses so you can
select the right device; keep that output private.

## Audio diagnostics and retention

The service emits one `Audio diagnostics:` JSON summary per ten-second reporting
window when measurements exist, plus remaining measurements at orderly shutdown.
Idle periods produce no diagnostic entries. Each window resets its counters and
maximums; audio can cross a window boundary, so compare several adjacent windows.
These summaries contain numeric counts, levels and timings, never microphone
recordings, transcript text, tool arguments or provider payloads. Existing activity
and generation entries place summaries in the conversation timeline.

- `capture_samples` counts 48 kHz microphone samples. `capture_overflows` counts
  PortAudio callbacks reporting lost input; it cannot recover or count the exact
  missing samples. `mic_raw` and `mic_processed` report sample count, RMS, peak
  and samples at the PCM clipping ceiling before and after resampling/gain.
- `handoff_*` counts 24 kHz PCM moving from the capture worker to the application.
  `input_not_listening_samples` identifies intentional rejection outside active
  listening (including the opening greeting). `input_accepted_samples` means the
  Live adapter accepted the call; `input_sent_samples` means the SDK append
  completed, which does **not** prove server recognition.
- `input_queue_frames` is the maximum queued 20 ms frames. `input_age_ms` measures
  enqueue-to-send-start delay; `input_send_ms` measures a completed SDK append.
  Capture and handoff queues have their own age/depth maxima. These are local
  queue measurements, not network round-trip times.
- `user_transcript_events` and `assistant_transcript_events` count fragments,
  not sentences or turns. `output_*` counts 24 kHz samples received, handed to the
  conversation, discarded by the adapter, or suppressed by conversation policy.
  Delivery to the conversation is not proof of speaker playback.
- `playback_written_samples` counts 48 kHz voice/mixed samples submitted
  successfully to the speaker; `background_written_samples` counts scanner-only
  output. Neither proves acoustic audibility. Playback submissions/discards are
  counted at 24 kHz before conversion. Queue cancellation and in-flight canceled
  SDK calls can leave delivery uncertain; discard counts describe known local
  disposal. Resampler buffers and failed native writes prevent an exact
  end-to-end sample balance.
- Session exit, speech gate, scanner and tool-result counters help distinguish
  idle timeout, cancellation and deliberately suppressed speech. `loop_lag_ms`
  measures lateness of the ten-second reporting timer, not every brief loop stall.

Use `make pi-logs` for recent service logs. For a bounded diagnostic export on the
Pi, run:

```sh
sudo journalctl --namespace=+blooglyblob -u blooglyblob --since '10 minutes ago' --no-pager
sudo journalctl --namespace=blooglyblob --disk-usage
```

Provisioning and updates install `/etc/systemd/journald@blooglyblob.conf`; the
service writes to that dedicated namespace. Journald rotates at 4 MiB per file,
uses a 64 MiB persistent budget, retains at most seven days of archived history,
and reserves 512 MiB free space. Size pressure can remove history sooner. The
volatile fallback budget is 8 MiB. Active files and journal overhead mean these
are journal budgets rather than byte-exact filesystem quotas. Normal messages
sync at most every 30 seconds, so abrupt power loss may lose the newest entries.

The policy covers this service's stdout/stderr as well as diagnostics. Other
services' retention is unchanged. Pre-upgrade entries remain in the default
journal under its existing policy; `+blooglyblob` includes those when reading.
Foreground `make pi-run` output goes to its terminal, not this retained journal.
There is no second application log file or custom rotation process.

## Local sound effects

The application opens bundled WAV files locally. Timer/doorbell alerts use
`sounds/alert_16k.wav`. Internet searches use `sounds/search_16k.wav`: a 30-second
electronic scanner that loops quietly until the search finishes or fails. The
audio controller prepares it during startup, then mixes it through the existing
conversation speaker writer. Voice energy lowers the scanner smoothly; its
background volume returns after a short speech pause. Speech and microphone
capture continue throughout. There is no minimum playback duration. Cancellation,
the button, generation flush and session failure stop it. Dance and alert
playback remain sequential.

Conversation and media modules own search activity and direct start/stop calls;
the audio controller owns mixing, looping and volume. Removing the background
effect confirms no more effect samples will be submitted, not that the speaker
has physically drained. Drain, flush and full release remain separate completion
boundaries. Background-only frames do not count toward speech playback progress.

Both recordings are synthesized without external samples and licensed under
[CC0](../../LICENSING.md). Their standard-library-only generators are MIT software:

```sh
python3 scripts/generate_alert_sound.py --output /tmp/alert-preview.wav
python3 scripts/generate_search_sound.py --output /tmp/search-preview.wav
```

Run these from the repository root. Each command overwrites its output file.
To replace a bundled sound, use its repository path as the output, update the
asset manifest and license hash, and run the deployment/package checks.
Dance playback remains local, using the song and its beat-timing file; see the
[beat analysis helper](beat-analysis.md) when preparing a replacement song.
