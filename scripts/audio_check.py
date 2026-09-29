#!/usr/bin/env python3
"""Brief audio diagnostics using the same device selection as the application."""

from array import array
import math
import sys


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
        if command == "test-mic":
            print("Recording three seconds; speak into the microphone.", flush=True)
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=rate,
                input=True,
                input_device_index=input_index,
            )
            try:
                samples = b"".join(stream.read(1600) for _ in range(90))
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
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=rate,
            output=True,
            output_device_index=output_index,
        )
        try:
            stream.write(samples)
        finally:
            stream.close()
    finally:
        audio.terminate()


if __name__ == "__main__":
    main(sys.argv[1])
