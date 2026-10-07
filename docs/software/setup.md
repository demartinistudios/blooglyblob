# Set up a Raspberry Pi

One application runs on the Pi, managed by `blooglyblob.service`. It uses
OpenAI over the internet; it is not an offline language model. The illustrated
build guide follows the same four stages below, before mounting the Pi.

## 1. Prepare the microSD card

Use a Raspberry Pi 3 Model A+ and Raspberry Pi OS Lite **64-bit**, based on
**Trixie with Python 3.13**. A Pi 3B+ has provided development evidence; final
physical qualification is still pending. Do not substitute a newer OS release
without checking support: the installer verifies the board, architecture, OS
and Python version.

On your computer, install Git, Make, Python 3.12 or newer, OpenSSH (`ssh`, `scp`)
and [Raspberry Pi Imager](https://www.raspberrypi.com/software/). Run terminal
commands in macOS/Linux, or inside [WSL on Windows](https://learn.microsoft.com/windows/wsl/install).
Use the same terminal environment throughout setup. Check that `python3`
selects your supported Python:

```sh
git --version
make --version
python3 --version
ssh -V
command -v scp
```

Use an existing SSH key from that environment. **Only if you need a new key**,
run the following and follow its prompts. Never overwrite an existing key;
answer no if prompted to replace one.

```sh
ssh-keygen -t ed25519
```

For the default key name, display the public key with:

```sh
cat ~/.ssh/id_ed25519.pub
```

If your existing key has another name, use its `.pub` path instead and ensure
its private key is selected by your SSH agent or an `IdentityFile` rule for this
Pi in the same terminal environment. Import only
this public-key line into Imager, never the private file without `.pub`. On
Windows, run Imager in Windows but paste the public key from WSL, or select that
WSL `.pub` file. A key suggested from the Windows account may not match the key
used by later WSL commands.

In Imager:

1. Choose Raspberry Pi 3, then Raspberry Pi OS Lite (64-bit). Confirm the
   description names Trixie.
2. Select the intended microSD card by name and capacity. Writing will erase
   that selected drive; stop if you cannot identify it confidently.
3. Choose a hostname and username, and keep both for SSH and `.env`. The examples
   below use `blooglyblob` and `builder`; replace them with your own choices.
   Set a private Pi password for any later sudo prompts.
4. Set Wi-Fi, country, time zone and keyboard layout in the controls provided by
   your Imager version. Enable SSH with public-key authentication and import the
   public key prepared above.
5. Review the device, OS, storage and settings. Write and verify the card, then
   eject it.

See Raspberry Pi's [installation instructions](https://www.raspberrypi.com/documentation/computers/getting-started.html)
for the Imager controls. No particular hostname or `pi` account is required.

## 2. Boot and connect

With power disconnected, insert the card. Rest the bare Pi on a clean,
nonconductive surface and connect a separate **5 V, 2.5 A micro-USB bench
supply** to its micro-USB power port. Allow a few minutes for first boot and
Wi-Fi. The computer must be able to reach the Pi on the network; the Pi also
needs internet access.

From your computer, substituting the identity you chose:

```sh
ssh builder@blooglyblob.local
```

If `.local` does not resolve, find the Pi in your router's device list and use
its IP address. A DHCP reservation can keep that address stable. On the first
connection, confirm you are contacting that Pi before accepting its host key.
Do not bypass a changed-host-key warning: verify a reimage or changed destination
before correcting `known_hosts`.

If SSH denies access, check the Imager username and that the imported public key
matches the key in your current terminal environment. A successful connection
shows a Pi shell prompt, for example `builder@blooglyblob:~ $`.

On the Pi, return to your computer terminal:

```sh
exit
```

Leave the Pi powered for configuration.

## 3. Configure BlooglyBlob

### Repository and target

On your computer, clone the repository and enter its folder. If you already have
a checkout, enter that folder instead of cloning inside it:

```sh
git clone https://github.com/demartinistudios/blooglyblob.git
cd blooglyblob
```

All subsequent Make commands run from this folder on your computer. Create the
settings files **only if absent**; these commands preserve existing files:

```sh
test -e .env || cp .env.example .env
test -e config/app.env || cp config/app.env.example config/app.env
```

Open `.env` in a text editor. Match the hostname/IP address and username that
worked for SSH; the example is:

```dotenv
PI_HOST=blooglyblob.local
PI_USER=builder
BLOOGLYBLOB_ENV_FILE=config/app.env
```

These are file contents, not shell commands. Do not add your Pi or Wi-Fi
password. An IP address or configured SSH alias also works. Explicit Make
invocation settings override exported environment values, which override the
saved root `.env`.

### OpenAI credentials

Create your own [OpenAI API key](https://platform.openai.com/api-keys) and enable
API billing. API usage is billed separately from a ChatGPT subscription. Your
account needs access to the configured models in `config/app.env.example`.
Application startup can make a billable greeting request; conversations and tool
requests also consume billable usage.

In your editor, put the key after `OPENAI_API_KEY=` in `config/app.env`. Keep the
other example settings. This file is ignored by Git; never commit it, share it
or include it in screenshots. Keep the path selected by `BLOOGLYBLOB_ENV_FILE`
in `.env`.

### USB audio selection

Connect the USB extension's male end to the Pi's USB-A socket, then connect the
loose audio module to its female socket. Keep the module in its case on the
bench. From the repository on your computer:

```sh
make pi-ssh
```

On the Pi:

```sh
cat /proc/asound/cards
```

Find the USB audio card and note the name after `USB-Audio -`. For example:

```text
1 [Device         ]: USB-Audio - USB PnP Audio Device
```

If no USB audio card appears, check the module and extension connections and
list the cards again. Also note the bracketed card ID (`Device` above). Use this
ID rather than the numeric index, which can change after reboot.

Set the playback level on the Pi. For the specified Waveshare module and
speakers, inspect its `Speaker` control, then set both playback channels to 100%
(0 dB) and save the setting:

```sh
amixer -c Device sget Speaker
amixer -c Device -- sset Speaker playback 100%
sudo alsactl store Device
```

Replace `Device` if your USB card has a different ID. Confirm both channels are
on and report `[100%]` and `[0.00dB]`. If the control is missing or has no dB
scale, stop here and inspect that module's controls with `alsamixer -c Device`.
At 100%, the module's 2.6 W per channel stays within the speakers' 3 W rating.
Recheck the level after reboot with `amixer -c Device sget Speaker`, and turn it
down if speech or music is too loud or distorted. If it is still too quiet at
100%, the module has a small volume screw inside its case (clockwise is louder;
see the [Waveshare FAQ](https://www.waveshare.com/wiki/USB_TO_AUDIO#FAQ)). Shut
down and disconnect power before opening the module. This is optional.

Leave the Pi shell:

```sh
exit
```

On your computer, edit `config/app.env` and set both audio names to the name
actually reported by your module. Remove the leading `#` if editing the
commented examples. For the example output above:

```dotenv
AUDIO_INPUT_DEVICE=USB PnP Audio Device
AUDIO_OUTPUT_DEVICE=USB PnP Audio Device
MIC_GAIN=1
```

The selected module provides both microphone and speaker audio. Names must
identify one input and one output unambiguously. A configured missing or
ambiguous device stops startup rather than silently choosing another device.
Start with `MIC_GAIN=1` (no extra software microphone amplification) for the new
module, then tune only after a voice test. It does not control speaker volume.
Provisioning preserves ALSA settings and does not retune volume.

## 4. Install, check and shut down

Use the bare Pi and loose USB audio module on the bench. **Keep all servo and
lighting circuits disconnected:** provisioning starts the application and there
is no software-only motion-disabled installation mode. Hardware tests and
[servo fitting](maintenance.md#commissioning-limits) happen later in assembly.

From the repository on your computer, check prerequisites:

```sh
make pi-check
```

The result must identify your intended Pi 3, `aarch64` or `arm64`, Python 3.13
and `VERSION_CODENAME=trixie`. If it fails, correct the SSH target or board/image
selection before continuing.

Install from your computer:

```sh
make pi-provision
```

Provisioning installs dependencies, the GPIO daemon and application service,
starts the application and enables it at boot. Sudo may request the Pi account's
password interactively; it is never stored in `.env`. There is no second
`pi-update` step needed for first installation. Existing remote configuration is
preserved on reruns.

### Reboot if provisioning requests it

If provisioning reports “Onboard audio is loaded and conflicts with GPIO18 LEDs”,
it has written an owned
module blacklist and needs a reboot. GPIO18 lighting cannot share PWM with
onboard analogue audio; see the driver's [PWM limitation](https://github.com/jgarff/rpi_ws281x#pwm).
No application files are replaced before this prerequisite passes.

On your computer:

```sh
make pi-ssh
```

On the Pi:

```sh
sudo reboot
```

SSH will disconnect. Wait for the Pi to rejoin Wi-Fi, then rerun
`make pi-provision` **on your computer**. If provisioning reports a different
error, fix that cause before continuing.

### Verify the service

On your computer:

```sh
make pi-status
```

Expect `active (running)`. Inspect the log next, especially if status is stopped
or failed:

```sh
make pi-logs
```

Press **Ctrl+C** to stop following logs and return to your computer prompt.
If the log reports missing credentials or an audio name, correct the installed
file; editing your computer's initial `config/app.env` no longer changes it.

For a configuration error, run `make pi-ssh` on your computer, then on the Pi:

```sh
sudoedit /etc/blooglyblob/app.env
```

Save and close the editor, type `exit`, then run on your computer:

```sh
make pi-restart
make pi-status
```

Do not mark setup complete until the application is running without configuration
errors. Do not run motion, microphone-recording or LED tests during bench setup.

### Shut down before mounting

On your computer:

```sh
make pi-ssh
```

On the Pi:

```sh
sudo poweroff
```

After SSH disconnects, wait for the green activity light to stop flashing.
Unplug the bench supply and USB audio lead before mounting the Pi and boards.

## Later assembly and operation

Follow the build guide's staged checks for the [supported LED chain](maintenance.md#supported-led-chain)
and [servo fitting](maintenance.md#commissioning-limits). With the head and arms
off the shafts, `make pi-servo-fit` holds the fit pose; type STOP, shut down and
unplug before fitting the parts. Runtime uses fixed 1000–2000 µs limits at 50 Hz;
saved calibration does not override them. An existing robot needs refitting if
its horns were installed for different calibrated positions.

`make pi-check-audio` can inspect audio devices after installation. Keep physical
tests in their assembly stages. The button starts a conversation; there are no
wake-word models or keys. Follow the [release checklist](../release/checklist.md)
before claiming a new build or replacement audio arrangement is supported.
