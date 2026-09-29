"""Direct hardware operations; importing this module never imports Pi drivers."""
import asyncio
from contextlib import ExitStack
from importlib.resources import as_file, files
import logging
import os
from pathlib import Path
import threading

from .lighting import LightingState
from .music_lights import load_lights
from .conversation_state import ConversationMode, ConversationState
from .local_media import HardwareReleaseError, LocalMedia, Worker

log = logging.getLogger(__name__)
ANIMATIONS = {name: name for name in ('wave_hello', 'celebrate', 'think', 'shrug', 'six_seven', 'attention')}
HEAD_SPEEDS = {'slow': .5, 'normal': 1., 'fast': 2.5}


def _servos():
    from .servo_controller import ServoController
    return ServoController()


def _leds(**kwargs):
    from .led_controller import LEDController
    return LEDController(**kwargs)


def _ambient(**kwargs):
    from .ambient_animator import AmbientAnimator
    return AmbientAnimator(**kwargs)


def _button():
    from gpiozero import Button
    from gpiozero.pins.pigpio import PiGPIOFactory
    from .config import gpio_config
    try:
        factory = PiGPIOFactory()
    except Exception:
        factory = None
    try:
        button = Button(gpio_config.BUTTON_PIN, pin_factory=factory, bounce_time=.02)
    except Exception:
        if factory:
            factory.close()
        raise
    # gpiozero does not own a caller-supplied pin factory.
    return button, factory


class HardwareController:
    """Loop-owned lifecycle, GPIO-safe mute, and independent presentation.

    Callbacks are synchronous loop callbacks: on_button(),
    on_dance_finished(activity_id), on_failure(activity_id, sanitized_reason).
    Activity authority remains with the caller; completions never change it.
    Optional factories use the native constructors' keyword arguments. The
    required button factory returns a button or (button, owned_pin_factory).
    """

    def __init__(self, audio, on_button=lambda: None, on_dance_finished=lambda _: None,
                 on_failure=lambda *_: None, *, media_dir=None,
                 servo_factory=_servos, led_factory=_leds, ambient_factory=_ambient,
                 button_factory=_button, operation_timeout=3.):
        self._loop = asyncio.get_running_loop()
        self.audio = audio
        self._on_button, self._on_dance, self._on_failure = on_button, on_dance_finished, on_failure
        self.presentation = ConversationState()
        self.lighting = LightingState(audio.presentation)
        self.music_lights = None
        self.lights_path = None
        self.animation_lock = threading.Lock()
        self.servos = self.leds = self.ambient = self.button = self._pin_factory = None
        self._servo_factory, self._led_factory = servo_factory, led_factory
        self._ambient_factory, self._button_factory = ambient_factory, button_factory
        self._media_dir = media_dir if media_dir is not None else os.getenv('BLOOGLYBLOB_MEDIA_DIR')
        self._resources = ExitStack()
        self.alert_path = self.dance_path = self.beats_path = self.search_path = None
        self._timeout = operation_timeout
        self.media = LocalMedia(audio, self, timeout=operation_timeout)
        self._prepared = self._closed = False
        self._prepare_task = None
        self._close_task = None
        self._native_workers: list[Worker] = []
        self._gestures: list[Worker] = []
        self._gesture_error = False
        self._ownership_uncertain = False

    @property
    def ownership_uncertain(self):
        """Permanent evidence that native work or device closure was not confirmed."""
        return self._ownership_uncertain or self.media.ownership_uncertain

    def _notify(self, callback, *args):
        try:
            callback(*args)
        except Exception:
            log.error('hardware_callback_failed')
            if callback is not self._on_failure:
                self.report_failure(None, 'hardware_callback_failed')

    def report_failure(self, identity, reason):
        self._notify(self._on_failure, identity, reason)

    def dance_finished(self, identity):
        if not self._closed:
            self._notify(self._on_dance, identity)

    async def _native(self, operation):
        worker = Worker(operation, 'hardware-lifecycle')
        self._native_workers.append(worker)
        try:
            return await worker.wait(self._timeout)
        except Exception:
            if worker.thread.is_alive() or isinstance(worker.error, HardwareReleaseError):
                self._ownership_uncertain = True
            raise

    def _paths(self):
        for attr, package, filename in (
            ('alert_path', 'sounds', 'alert_16k.wav'),
            ('search_path', 'sounds', 'search_16k.wav'),
            ('dance_path', 'songs', 'dance_song.wav'),
            ('beats_path', 'songs', 'dance_song_beats.json'),
            ('lights_path', 'songs', 'dance_song_lights.json'),
        ):
            path = (Path(self._media_dir) / package / filename if self._media_dir is not None else
                    self._resources.enter_context(as_file(files(package).joinpath(filename))))
            setattr(self, attr, path)
            if not path.is_file():
                log.warning('Local media resource unavailable: %s', filename)

    async def prepare(self):
        if self._closed:
            raise RuntimeError('Hardware closed')
        if self._prepare_task is None:
            self._prepare_task = asyncio.create_task(self._prepare())
            self._prepare_task.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)
        await asyncio.shield(self._prepare_task)

    async def _prepare(self):
        try:
            await self._native(self._initialize)
            if not self._closed:
                self._prepared = True
        except Exception:
            self.report_failure(None, 'hardware_prepare_failed')
            # Clean up partial constructors only once initialization has exited.
            if all(not worker.thread.is_alive() for worker in self._native_workers):
                await self._native(self._cleanup)
            raise RuntimeError('hardware_prepare_failed') from None

    def _initialize(self):
        self._paths()
        self.music_lights = load_lights(self.dance_path, self.lights_path)
        try:
            self.servos = self._servo_factory()
        except HardwareReleaseError:
            raise
        except Exception:
            log.warning('Optional servo initialization failed')
        try:
            self.leds = self._led_factory(lighting=self.lighting)
            if self.leds:
                self.leds.on_failure = self._native_failure
                self.leds.start()
        except Exception:
            log.warning('Optional LED initialization failed')
            if self.leds:
                self.leds.cleanup()  # A failed stop must abort preparation.
                self.leds = None
        if self.servos:
            try:
                self.ambient = self._ambient_factory(servo_controller=self.servos,
                    conversation_state=self.presentation, animation_lock=self.animation_lock)
                if self.ambient:
                    self.ambient.on_failure = self._native_failure
                    self.ambient.start()
            except Exception:
                log.warning('Optional ambient initialization failed')
                if self.ambient:
                    self.ambient.stop()
                    self.ambient = None
        result = self._button_factory()
        if isinstance(result, tuple):
            self.button, self._pin_factory = result
        else:
            self.button = result
        if self.button is None:
            raise RuntimeError('Required button unavailable')
        self.button.when_pressed = self._button_pressed

    def _native_failure(self, reason):
        try:
            self._loop.call_soon_threadsafe(self.report_failure, None, reason)
        except RuntimeError:
            log.error('hardware_failure_loop_unavailable')

    def _button_pressed(self):
        if self._closed or not self._prepared:
            return
        self.audio.mute()
        self.mute_media()
        try:
            self._loop.call_soon_threadsafe(self._button_decision)
        except RuntimeError:
            log.error('hardware_button_loop_unavailable')

    def _button_decision(self):
        if not self._closed:
            self._notify(self._on_button)

    def mute_media(self):
        self.media.mute()

    async def stop_media(self):
        await self.media.stop()

    async def chime(self, activity_id):
        if self._closed or not self._prepared or self.ownership_uncertain:
            raise RuntimeError('Hardware not ready or ownership uncertain')
        await self.media.chime(activity_id)

    def start_dance(self, activity_id=None):
        if self._closed or not self._prepared or self.ownership_uncertain:
            raise RuntimeError('Hardware not ready or ownership uncertain')
        return self.media.start_dance(activity_id)

    def set_level(self, level):
        """Thread-safe voice presentation only; never touches capture."""
        self.presentation.audio_level = level

    def present(self, state):
        mode = ConversationMode(state)
        self.presentation.mode = mode
        if mode == ConversationMode.IDLE and self.servos and not self.media.dancing:
            self._gesture(self._idle_pose)

    def light(self, mode):
        """LED-only lifecycle; never changes servo or microphone state."""
        if self._closed:
            return
        if mode == 'fault' and (not self.leds or not self.leds.running):
            return
        self.lighting.set_mode(mode)

    def pending_light(self, identity, active):
        self.lighting.pending(identity, active)

    def _idle_pose(self):
        self.servos.head.center()
        self.servos.left_arm.down()
        self.servos.right_arm.down()

    def _gesture_done(self, worker):
        if worker.error:
            self._gesture_error = True
            self.report_failure(None, 'gesture_failed')

    def _gesture(self, operation):
        if self._closed or self.ownership_uncertain or self.media.dancing or not self.animation_lock.acquire(blocking=False):
            return False
        # Retain only unfinished workers; errors are latched by their loop callback.
        self._gesture_error |= any(worker.error is not None for worker in self._gestures)
        self._gestures = [worker for worker in self._gestures if worker.thread.is_alive()]
        def run():
            try:
                operation()
            finally:
                self.animation_lock.release()
        try:
            worker = Worker(run, 'hardware-gesture')
        except Exception:
            self.animation_lock.release()
            raise
        self._gestures.append(worker)
        worker.done.add_done_callback(lambda _: self._loop.call_soon_threadsafe(self._gesture_done, worker))
        return True

    async def wait_gestures(self):
        errors = []
        for worker in self._gestures:
            try:
                await worker.wait(self._timeout)
            except RuntimeError as exc:
                errors.append(exc)
        live = [worker for worker in self._gestures if worker.thread.is_alive()]
        self._gestures = live
        await asyncio.sleep(0)  # Deliver matching worker-error callbacks.
        if live:
            self._ownership_uncertain = True
            self.report_failure(None, 'gesture_release_timeout')
            raise RuntimeError('gesture_release_timeout')
        if errors or self._gesture_error:
            self._gesture_error = False
            raise RuntimeError('gesture_failed')

    async def execute(self, name, params):
        if self._closed or self.ownership_uncertain:
            raise RuntimeError('Hardware closed or ownership uncertain')
        if name == 'goToSleep':
            return 'Going to sleep'
        if name == 'danceMode':
            return self.start_dance(params.get('activity_id'))
        if name == 'playAnimation':
            animation = params.get('animation', '').lower()
            if animation not in ANIMATIONS:
                return f"Error: Unknown animation '{animation}'"
            if self.servos is None:
                return 'Error: Servo controller not initialized'
            def animate():
                getattr(self.servos, ANIMATIONS[animation])()
                if self.ambient:
                    self.ambient.hold_all(5.)
            if not self._gesture(animate):
                return 'Error: Animation already playing'
            return f'Playing {animation}'
        if name == 'moveHead':
            direction = params.get('direction', '').lower()
            if direction not in {'left', 'right', 'center'}:
                return f"Error: Invalid direction '{direction}'"
            if self.servos is None:
                return 'Error: Servo controller not initialized'
            speed = HEAD_SPEEDS.get(params.get('speed', 'normal').lower(), 1.)
            def move():
                getattr(self.servos.head, {'left':'look_left', 'right':'look_right', 'center':'center'}[direction])(speed=speed)
                if self.ambient:
                    self.ambient.hold_head(5.)
            self._gesture(move)
            return f'Moving head {direction}'
        return f"Error: Unknown tool '{name}'"

    async def rest(self):
        if self.servos:
            if not self._gesture(self.servos.rest):
                raise RuntimeError('Animation already playing')
            await self.wait_gestures()

    async def detach_all(self):
        if self.servos:
            if not self._gesture(self.servos.detach_all):
                raise RuntimeError('Animation already playing')
            await self.wait_gestures()

    def _cleanup(self, *, motion_owned=False):
        errors = []
        # Ambient failure must prevent servo cleanup while it may still move.
        ambient_stopped = True
        for attr, operation in (('button', 'close'), ('_pin_factory', 'close'),
                                ('ambient', 'stop'), ('leds', 'cleanup'), ('servos', 'cleanup')):
            resource = getattr(self, attr)
            if resource is None or (motion_owned and attr in {'ambient', 'leds', 'servos'}) or (attr == 'servos' and not ambient_stopped):
                continue
            try:
                if attr == 'button':
                    resource.when_pressed = None
                getattr(resource, operation)()
                setattr(self, attr, None)
            except Exception:
                errors.append(attr)
                if attr == 'ambient':
                    ambient_stopped = False
        if errors:
            raise HardwareReleaseError('hardware_cleanup_failed')
        if not motion_owned:
            self._resources.close()

    async def close(self):
        if self._close_task is None:
            self._closed = True
            self.lighting.stop()
            self.mute_media()
            self._close_task = asyncio.create_task(self._close())
            self._close_task.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)
        await asyncio.shield(self._close_task)

    async def _close(self):
        errors = []
        if self._prepare_task:
            try:
                await asyncio.shield(self._prepare_task)
            except Exception:
                pass
        for worker in self._native_workers:
            if worker.thread.is_alive():
                try:
                    await worker.wait(self._timeout)
                except Exception:
                    self.report_failure(None, 'hardware_release_failed')
                    raise RuntimeError('hardware_release_failed') from None
        try:
            await self.media.close()
        except Exception:
            errors.append('hardware_release_failed')
        try:
            await self.wait_gestures()
        except Exception:
            if self.ownership_uncertain:
                errors.append('hardware_release_failed')
            else:
                log.warning('Completed gesture failed; hardware ownership released')
        # Retiring media may still be preparing or using LEDs/servos. Keep its
        # dependencies and resource contexts alive even before it takes the lock.
        media_owned = self.media.active and any(worker.thread.is_alive() for worker in self.media.active.workers)
        motion_owned = bool(self.animation_lock.locked() or media_owned)
        try:
            await self._native(lambda: self._cleanup(motion_owned=motion_owned))
        except Exception:
            errors.append('hardware_cleanup_failed')
        if motion_owned:
            self._ownership_uncertain = True
            errors.append('hardware_release_failed')
        if errors:
            self.report_failure(None, errors[0])
            raise RuntimeError(errors[0])
