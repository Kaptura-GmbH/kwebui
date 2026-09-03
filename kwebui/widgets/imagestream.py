"""ImageStream widget: a live MJPEG feed (webcam, OpenCV, or manual push).

Deliberately separate from ``image.py`` -- a static picture and a live
feed have nothing in common on the wire (one file fetch vs. an
open-ended multipart HTTP stream), so sharing a plugin would only add
branching, not save code.

Two ways to feed frames:
  * push model  -- call ``widget.push_frame(jpeg_bytes)`` yourself,
    e.g. from a background thread reading a webcam with OpenCV.
  * pull model  -- pass ``frame_provider`` (a zero-arg callable returning
    JPEG bytes) and kwebui polls it at ``fps`` on your behalf. ``fps`` can
    be changed live with ``widget.set_fps(...)`` -- no restart needed --
    and ``fps=None``/``0`` means unthrottled: poll as fast as
    ``frame_provider`` itself can produce frames.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, AsyncIterator, Callable

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from ..plugin import WidgetPlugin
from ..widget import Widget

if TYPE_CHECKING:
    from ..app import KApp

_BOUNDARY = b"--frame"


class ImageStreamWidget(Widget):
    def __init__(self, widget_id: str, widget_type: str, props: dict) -> None:
        super().__init__(widget_id, widget_type, props)
        self._latest_frame: bytes | None = None
        self._frame_ready = asyncio.Event()
        self._provider_task: asyncio.Task | None = None

    def push_frame(self, jpeg_bytes: bytes) -> None:
        """Publish a new JPEG frame to every connected viewer. Thread-safe."""
        loop = self._app._loop if self._app else None
        if loop is None:
            self._set_latest(jpeg_bytes)
        else:
            loop.call_soon_threadsafe(self._set_latest, jpeg_bytes)

    def latest_frame(self) -> bytes | None:
        """The most recently published JPEG frame, or None before the first one arrives."""
        return self._latest_frame

    def set_fps(self, fps: float | None) -> "ImageStreamWidget":
        """Change the pull-model poll rate. Takes effect on the next frame,
        no restart needed. ``None`` or <= 0 means unthrottled (max speed)."""
        self.update(fps=fps)
        return self

    def set_width(self, width: float) -> "ImageStreamWidget":
        """Resize the stream viewer. -1 or 0 falls back to the frame's own
        size. Ignored while ``stretch`` is True."""
        self.update(width=width)
        return self

    def set_stretch(self, stretch: bool) -> "ImageStreamWidget":
        """Toggle whether the viewer fills its parent container's width."""
        self.update(stretch=stretch)
        return self

    def _set_latest(self, jpeg_bytes: bytes) -> None:
        self._latest_frame = jpeg_bytes
        self._frame_ready.set()
        self._frame_ready.clear()

    def _ensure_provider_running(self) -> None:
        provider = self.props.get("frame_provider")
        if provider is None or self._provider_task is not None:
            return
        self._provider_task = asyncio.create_task(self._run_provider(provider))

    async def _run_provider(self, provider: Callable[[], bytes]) -> None:
        loop = asyncio.get_running_loop()
        while True:
            started = loop.time()
            try:
                frame = await loop.run_in_executor(None, provider)
            except Exception:
                # A provider that raises instead of returning b"" (e.g. a
                # camera's get_image() timing out right after stream_on())
                # must not kill this loop -- there would be no restart:
                # _ensure_provider_running() only ever starts it once, so an
                # unhandled exception here would freeze the stream forever
                # with no visible error. Treat it like a dropped frame.
                frame = None
            if frame:
                self.push_frame(frame)

            # Re-read fps every iteration (not once before the loop) so
            # set_fps()/update(fps=...) takes effect on the very next frame.
            fps = self.props.get("fps", 10)
            if fps is None or fps <= 0:
                continue  # unthrottled: go straight to the next frame

            # Target a fixed period rather than adding a flat sleep on top
            # of however long capture+encode took, so the requested fps is
            # what you actually get instead of a ceiling you never reach.
            remaining = (1 / fps) - (loop.time() - started)
            if remaining > 0:
                await asyncio.sleep(remaining)


async def _mjpeg_chunks(widget: ImageStreamWidget) -> AsyncIterator[bytes]:
    while True:
        await widget._frame_ready.wait()
        frame = widget._latest_frame
        if frame is not None:
            yield _BOUNDARY + b"\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n"


class ImageStreamPlugin(WidgetPlugin):
    """
    Example (push model, e.g. from a webcam thread):
        stream = app.imagestream()
        stream.push_frame(jpeg_bytes)

    Example (pull model, kwebui polls for you):
        stream = app.imagestream(frame_provider=capture_jpeg_from_camera, fps=15)
        stream.set_fps(0)   # switch to unthrottled (max speed) at any time
    """

    widget_name = "imagestream"

    def create(
        self,
        widget_id: str,
        *,
        frame_provider: Callable[[], bytes] | None = None,
        fps: float | None = 10,
        width: float = -1,
        stretch: bool = False,
    ) -> ImageStreamWidget:
        props = {"fps": fps, "frame_provider": frame_provider, "width": width, "stretch": stretch}
        return ImageStreamWidget(widget_id, self.widget_name, props)

    def register_routes(self, fastapi_app: "FastAPI", app: "KApp") -> None:
        @fastapi_app.get("/stream/{widget_id}")
        async def mjpeg_stream(widget_id: str) -> StreamingResponse:
            widget = app.page.find(widget_id)
            if not isinstance(widget, ImageStreamWidget):
                raise HTTPException(status_code=404, detail="Stream not found")
            widget._ensure_provider_running()
            return StreamingResponse(
                _mjpeg_chunks(widget),
                media_type="multipart/x-mixed-replace; boundary=frame",
            )
