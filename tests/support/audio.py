import threading


class Stream:
    def __init__(self):
        self.frames = []
        self.writing = threading.Event()
        self.allow_write = threading.Event()
        self.allow_write.set()
        self.draining = threading.Event()
        self.allow_drain = threading.Event()
        self.allow_drain.set()
        self.fail = False

    def write(self, pcm):
        self.writing.set()
        self.allow_write.wait(2)
        if self.fail:
            raise RuntimeError("private native message")
        self.frames.append(pcm)

    def stop_stream(self):
        self.draining.set()
        self.allow_drain.wait(2)

    def start_stream(self):
        pass


class Driver:
    def __init__(self):
        self.out_stream = Stream()
        self.stopped = False

    def start(self, on_input, on_failure):
        self.on_input, self.on_failure = on_input, on_failure

    def stop(self):
        self.stopped = True
