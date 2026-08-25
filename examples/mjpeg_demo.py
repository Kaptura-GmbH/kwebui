"""Live MJPEG stream with a snapshot button. Run with:

    pip install -e ".[imagestream]"
    python examples/mjpeg_demo.py

Then open the printed URL (default http://127.0.0.1:8701, or the next
free port after it) in a browser. If a webcam is available
at index 0 it is streamed live; otherwise a synthetic animated pattern
is generated so the demo still works on a machine with no camera.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import cv2
import numpy as np

from kwebui import KApp

THUMB_DIR = Path(tempfile.gettempdir()) / "kwebui_mjpeg_demo"
THUMB_DIR.mkdir(exist_ok=True)

THUMB_SIZE = (160, 120)


def _open_camera() -> cv2.VideoCapture | None:
    camera = cv2.VideoCapture(0)
    if camera.isOpened():
        return camera
    camera.release()
    return None


def _synthetic_frame(counter: int) -> np.ndarray:
    frame = np.full((240, 320, 3), (32, 32, 32), dtype=np.uint8)
    cx = 40 + (counter * 4) % 240
    cv2.circle(frame, (cx, 120), 30, (37, 99, 235), -1)
    cv2.putText(frame, time.strftime("%H:%M:%S"), (10, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    return frame


def _placeholder_frame() -> np.ndarray:
    frame = np.full((*THUMB_SIZE[::-1], 3), (24, 24, 24), dtype=np.uint8)
    cv2.putText(frame, "no snapshot yet", (8, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 150, 150), 1, cv2.LINE_AA)
    return frame


class MjpegDemo(KApp):
    def build(self) -> None:
        self.text("MJPEG Stream Demo", size=28, bold=True)
        self.text(
            "Live feed on top, captured snapshot below.",
            color="#6b7280",
        )

        self._camera = _open_camera()
        self._frame_count = 0
        self._capture_count = 0

        self.stream = self.imagestream(frame_provider=self._next_frame, fps=30, stretch=True)

        self.button("Capture Snapshot", on_click=self.on_capture)

        placeholder_path = THUMB_DIR / "placeholder.jpg"
        cv2.imwrite(str(placeholder_path), _placeholder_frame())
        self.snapshot = self.image(str(placeholder_path))

    def _next_frame(self) -> bytes:
        frame = None
        if self._camera is not None:
            ok, frame = self._camera.read()
            if not ok:
                frame = None
        if frame is None:
            frame = _synthetic_frame(self._frame_count)
        self._frame_count += 1
        ok, jpeg = cv2.imencode(".jpg", frame)
        return jpeg.tobytes() if ok else b""

    def on_capture(self) -> None:
        frame_bytes = self.stream.latest_frame()
        if not frame_bytes:
            return
        frame = cv2.imdecode(np.frombuffer(frame_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        thumbnail = cv2.resize(frame, THUMB_SIZE)

        self._capture_count += 1
        path = THUMB_DIR / f"capture_{self._capture_count}.jpg"
        cv2.imwrite(str(path), thumbnail)

        self.snapshot.set_source(str(path))
        # `set_source` always maps to the same `/media/{id}` URL, so the
        # browser won't refetch an unchanged src -- bump a cache-busting
        # query param to force it to reload the new file.
        self.snapshot.update(src=f"/media/{self.snapshot.id}?v={self._capture_count}")


if __name__ == "__main__":
    MjpegDemo(title="kwebui MJPEG Demo", width=900).run()
