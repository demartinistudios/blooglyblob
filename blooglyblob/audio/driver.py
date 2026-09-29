"""Lazy PortAudio driver and shared PCM/device selection utilities."""

import os
import queue
import threading

import numpy as np

from .resampler import DEVICE_SAMPLE_RATE, SPEECH_SAMPLE_RATE, PCMResampler


def _select_device(devices, setting, channels, baseline, selected=None):
    """Resolve one channel-capable device, preserving the existing USB default."""
    if selected is not None:
        if not 0 <= selected < len(devices) or devices[selected][channels] <= 0:
            raise RuntimeError(f"Invalid {setting} device index")
        return selected
    name = os.environ.get(setting, "").strip().lower()
    matches = [
        i
        for i, info in enumerate(devices)
        if info[channels] > 0 and (name or baseline) in info["name"].lower()
    ]
    if not matches or (name and len(matches) != 1):
        raise RuntimeError(
            f"{setting} must identify one available audio device; "
            "inspect the listed devices and configure capture/playback separately"
        )
    print(f"  {setting}: {devices[matches[0]]['name']}")
    return matches[0]


def select_input_device(pa, *, devices=None) -> int:
    """Resolve configured capture without opening a stream."""
    if devices is None:
        devices = [pa.get_device_info_by_index(i) for i in range(pa.get_device_count())]
    return _select_device(
        devices, "AUDIO_INPUT_DEVICE", "maxInputChannels", "usb pnp sound device"
    )


def select_output_device(pa, selected: int | None = None, *, devices=None) -> int:
    """Use the same configured speaker for conversation, dance, and alerts."""
    if devices is None:
        devices = [pa.get_device_info_by_index(i) for i in range(pa.get_device_count())]
    return _select_device(
        devices, "AUDIO_OUTPUT_DEVICE", "maxOutputChannels", "usb", selected
    )


class AudioDriver:
    """One continuous duplex device lifetime, owned by AudioController."""

    def __init__(self):
        self.p = self.in_stream = self.out_stream = None
        self._thread = None
        self._stop = threading.Event()
        self._raw = queue.Queue(maxsize=128)
        self._resampler = PCMResampler(DEVICE_SAMPLE_RATE, SPEECH_SAMPLE_RATE)

    def start(self, on_input, on_failure):
        import pyaudio

        self._gain = int(os.environ.get("MIC_GAIN", "10"))
        self._on_input, self._on_failure = on_input, on_failure
        self.p = pyaudio.PyAudio()
        devices = [
            self.p.get_device_info_by_index(i) for i in range(self.p.get_device_count())
        ]
        input_index = select_input_device(self.p, devices=devices)
        output_index = select_output_device(self.p, devices=devices)

        def capture(data, frame_count, time_info, status):
            if not self._stop.is_set():
                try:
                    self._raw.put_nowait(data)
                except queue.Full:
                    self._stop.set()
                    on_failure("input_overflow")
            return None, pyaudio.paContinue

        self.in_stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=DEVICE_SAMPLE_RATE,
            input=True,
            input_device_index=input_index,
            frames_per_buffer=2048,
            stream_callback=capture,
        )
        self.out_stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=DEVICE_SAMPLE_RATE,
            output=True,
            output_device_index=output_index,
            frames_per_buffer=1000,
            start=True,
        )
        self._thread = threading.Thread(
            target=self._capture, daemon=True, name="audio-capture"
        )
        self._thread.start()

    def _capture(self):
        gain = self._gain
        while not self._stop.is_set():
            try:
                pcm = self._raw.get(timeout=0.1)
                pcm = self._resampler.process(pcm)
                if gain > 1:
                    samples = np.frombuffer(pcm, dtype=np.int16)
                    pcm = (
                        np.clip(samples.astype(np.int32) * gain, -32767, 32767)
                        .astype(np.int16)
                        .tobytes()
                    )
                self._on_input(pcm)
            except queue.Empty:
                continue
            except Exception:
                self._stop.set()
                self._on_failure("capture_failed")

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
            if self._thread.is_alive():
                raise RuntimeError("Audio capture worker did not stop")
        for name in ("in_stream", "out_stream"):
            stream = getattr(self, name)
            if stream:
                stream.stop_stream()
                stream.close()
                setattr(self, name, None)
        if self.p:
            self.p.terminate()
            self.p = None
