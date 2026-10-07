#!/usr/bin/env python3
"""Brief audio diagnostics using the same device selection as the application."""

from array import array
import math
import sys
import time


def main(command):
    from blooglyblob.config import load_runtime_environment, validate_settings
    import os

    load_runtime_environment()
    validate_settings(os.environ)
    from blooglyblob.audio.driver import select_input_device, select_output_device
    import pyaudio

    audio = pyaudio.PyAudio()
    try:
        devices = [
            audio.get_device_info_by_index(i) for i in range(audio.get_device_count())
        ]
        for index, info in enumerate(devices):
            print(
                f"    [{index}] {info['name']} "
                f"(in={info['maxInputChannels']}, out={info['maxOutputChannels']})"
            )
        input_index = select_input_device(audio, devices=devices)
        output_index = select_output_device(audio, devices=devices)
        if command == "check-audio":
            return
        rate = 48000

        def play(samples):
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=rate,
                output=True,
                output_device_index=output_index,
            )
            try:
                stream.write(samples)
                # Drain playback before recording or releasing the device.
                stream.stop_stream()
            finally:
                stream.close()

        if command == "test-mic":
            print("After the beep, speak for five seconds.", flush=True)
            cue_frames = int(rate * 0.2)
            fade_frames = int(rate * 0.005)
            cue = array(
                "h",
                (
                    int(
                        1500
                        * min(1, i / fade_frames, (cue_frames - 1 - i) / fade_frames)
                        * math.sin(2 * math.pi * 660 * i / rate)
                    )
                    for i in range(cue_frames)
                ),
            ).tobytes()
            play(cue)
            time.sleep(0.3)  # Let the cue decay before opening the microphone.
            print("Recording five seconds...", flush=True)
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=rate,
                input=True,
                input_device_index=input_index,
            )
            try:
                samples = b"".join(stream.read(1600) for _ in range(150))
            finally:
                stream.close()
        else:
            # Low-level tone: diagnostics must not silently retune hardware gain.
            samples = array(
                "h",
                (
                    int(1500 * math.sin(2 * math.pi * 440 * i / rate))
                    for i in range(rate)
                ),
            ).tobytes()
        print("Playing through the configured speaker.", flush=True)
        play(samples)
    finally:
        audio.terminate()


if __name__ == "__main__":
    main(sys.argv[1])
