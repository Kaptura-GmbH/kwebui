"""Camera streaming that never waits on the UI. Run with:

    python examples/demo_nonblocking.py

The main loop grabs frames from a Daheng camera (falls back to an
animated synthetic frame if gxipy or the camera isn't available, so
this runs on any machine) and just keeps a "latest frame" buffer
up to date, completely independent of kwebui. Press SPACE in the
terminal to start the kwebui viewer in the background -- it comes up on
http://127.0.0.1:8701 and pulls frames from that same buffer. The
capture loop never blocks on it, before or after it starts.

Does kwebui need its own thread, or can this be done with FastAPI alone?
Here it needs its own thread: the capture loop above is a plain
synchronous while-loop, and `KApp.run()` is *also* a blocking call
(`uvicorn.Server(...).run()` under the hood, which does its own
`asyncio.run`) -- two blocking calls can't share one thread. A daemon
thread for kwebui's server is the fix, started only once, on demand.
The alternative -- rewriting the capture loop around asyncio and
mounting kwebui's `build_fastapi_app()` into that same event loop
(camera reads via `loop.run_in_executor`) -- avoids the thread, but only
by asyncio-ifying code that has no other reason to be asyncio. Not
worth it here.
"""
from __future__ import annotations

import math
import select
import sys
import termios
import threading
import time
import tty

import cv2
import numpy as np

from kwebui import KApp

try:
    import gxipy as gx
except ImportError:
    gx = None


class CameraStreamer:
    """Owns the camera and the latest encoded frame. Knows nothing about kwebui."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest_jpeg = b""
        self._frame_count = 0
        self._cam = None
        # DeviceManager de-initializes the underlying camera API library
        # once its last reference is garbage collected, so it must stay
        # alive for as long as `self._cam` is in use.
        self._device_manager = None
        if gx is not None:
            self._device_manager = gx.DeviceManager()
            _, devices = self._device_manager.update_device_list()
            if devices:
                self._cam = self._device_manager.open_device_by_sn(devices[0]["sn"])
                self._cam.TriggerMode.set(gx.GxSwitchEntry.OFF)
                self._cam.stream_on()

    def capture_once(self) -> None:
        """Grab (or synthesize) one frame and store it JPEG-encoded."""
        frame = self._read_camera_frame() if self._cam is not None else self._synthetic_frame()
        ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            with self._lock:
                self._latest_jpeg = jpeg.tobytes()
                self._frame_count += 1

    def latest_jpeg(self) -> bytes:
        """Zero-arg callable handed to kwebui as `frame_provider` -- just
        returns whatever the main loop last captured, no camera access."""
        with self._lock:
            return self._latest_jpeg

    def frame_count(self) -> int:
        with self._lock:
            return self._frame_count

    def _read_camera_frame(self) -> np.ndarray:
        cam = self._cam
        raw_image = cam.data_stream[0].get_image(200)
        if raw_image is None:
            return self._synthetic_frame()
        if cam.PixelColorFilter.is_implemented():
            numpy_image = raw_image.convert("RGB").get_numpy_array()
            return cv2.cvtColor(numpy_image, cv2.COLOR_RGB2BGR)
        return cv2.cvtColor(raw_image.get_numpy_array(), cv2.COLOR_GRAY2BGR)

    def _synthetic_frame(self) -> np.ndarray:
        frame = np.full((240, 320, 3), (30, 30, 30), dtype=np.uint8)
        x = int(160 + 100 * math.sin(time.monotonic()))
        cv2.circle(frame, (x, 120), 20, (80, 160, 250), -1)
        cv2.putText(frame, "no camera - synthetic feed", (10, 220),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 150, 150), 1, cv2.LINE_AA)
        return frame

    def close(self) -> None:
        if self._cam is not None:
            self._cam.stream_off()
            self._cam.close_device()


class StreamViewer(KApp):
    """Thin visualization layer -- built and `.run()` only when needed."""

    def __init__(self, streamer: CameraStreamer, **kwargs) -> None:
        self._streamer = streamer
        super().__init__(**kwargs)

    def build(self) -> None:
        self.text("Live Camera Stream", size=24, bold=True)
        self.imagestream(frame_provider=self._streamer.latest_jpeg, fps=20)


def _space_pressed() -> bool:
    """Non-blocking single-key check: True the instant SPACE is waiting
    on stdin, without waiting for Enter and without blocking the loop."""
    ready, _, _ = select.select([sys.stdin], [], [], 0)
    return bool(ready) and sys.stdin.read(1) == " "


def main() -> None:
    streamer = CameraStreamer()
    viewer_started = False

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    print("Streaming... press SPACE to open the kwebui viewer, Ctrl+C to quit.")
    try:
        while True:
            streamer.capture_once()

            if streamer.frame_count() % 30 == 0:
                print(f"main loop: {streamer.frame_count()} frames captured")

            if _space_pressed() and not viewer_started:
                viewer_started = True
                viewer = StreamViewer(streamer, title="Live Stream Viewer")
                threading.Thread(target=viewer.run, daemon=True).start()
                print("SPACE pressed -- kwebui viewer starting in the background.")

            if streamer._cam is None:
                time.sleep(0.03)  # keep the synthetic loop from pegging a core
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        streamer.close()


if __name__ == "__main__":
    main()
