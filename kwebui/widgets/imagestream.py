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

``fps`` is a *capture* rate. ``max_send_fps`` is separate, and caps what
each viewer is actually sent -- useful when the provider is deliberately
fast (a camera grabbing at 200 fps) but a browser cannot paint more than
its display refreshes anyway. Frames in between are dropped rather than
queued, so a slow viewer stays on the newest frame instead of falling
progressively behind. See ``_mjpeg_chunks``.
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

    def set_max_send_fps(self, max_send_fps: float | None) -> "ImageStreamWidget":
        """Cap how many frames per second are sent to each viewer, without
        touching how fast ``frame_provider`` is polled. ``None`` or <= 0
        means no cap (send every frame). Takes effect on the next frame."""
        self.update(max_send_fps=max_send_fps)
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


async def _mjpeg_chunks(
    widget: ImageStreamWidget, cancel: asyncio.Event | None = None
) -> AsyncIterator[bytes]:
    loop = asyncio.get_running_loop()
    last_sent = float("-inf")
    while True:
        if cancel is not None and cancel.is_set():
            # Severed from the server side (see register_routes) -- this
            # must never depend on the *client's* JS running, because the
            # one thing that can make a browser's main thread too busy to
            # ever run that JS is this very connection: measured, a
            # sufficiently fast/large MJPEG feed pegs Firefox's main
            # thread hard enough that literally no script executes again,
            # not even a bare property write -- so the client can never be
            # the one to hang up. Ending the generator here closes the
            # StreamingResponse and the underlying TCP connection
            # regardless of what the browser is doing.
            return
        if cancel is not None:
            # Re-check `cancel` periodically even with no new frame, so a
            # provider that stalls doesn't also stall the teardown.
            try:
                await asyncio.wait_for(widget._frame_ready.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
        else:
            await widget._frame_ready.wait()

        # Throttle what goes down the wire, independently of how fast
        # frames are produced. Capturing at 200 fps can be entirely
        # reasonable (that is the provider's business), but *sending* at
        # 200 fps to a browser is not: measured, Chromium paints at most
        # ~60/s no matter how many frames it is fed, and Firefox does far
        # worse -- at 100 fps of 1440x1080 JPEG its main thread already
        # stalls for seconds at a time, and at 200 fps the page stops
        # responding altogether, because it accepts every frame off the
        # socket and queues them faster than it can decode them.
        max_fps = widget.props.get("max_send_fps")
        if max_fps:
            remaining = (1 / max_fps) - (loop.time() - last_sent)
            if remaining > 0:
                await asyncio.sleep(remaining)

        # Read the frame *after* any wait, never before: the point of
        # skipping frames is to show the newest one, so a viewer that
        # cannot keep up falls behind by nothing rather than working
        # through a backlog.
        frame = widget._latest_frame
        if frame is not None:
            last_sent = loop.time()
            yield _BOUNDARY + b"\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n"


class ImageStreamPlugin(WidgetPlugin):
    """
    Example (push model, e.g. from a webcam thread):
        stream = app.imagestream()
        stream.push_frame(jpeg_bytes)

    Example (pull model, kwebui polls for you):
        stream = app.imagestream(frame_provider=capture_jpeg_from_camera, fps=15)
        stream.set_fps(0)   # switch to unthrottled (max speed) at any time

    Example (grab fast, but do not flood the browser):
        stream = app.imagestream(frame_provider=grab, fps=200, max_send_fps=60)
    """

    widget_name = "imagestream"

    def create(
        self,
        widget_id: str,
        *,
        frame_provider: Callable[[], bytes] | None = None,
        fps: float | None = 10,
        max_send_fps: float | None = None,
        width: float = -1,
        stretch: bool = False,
    ) -> ImageStreamWidget:
        props = {
            "fps": fps,
            "max_send_fps": max_send_fps,
            "frame_provider": frame_provider,
            "width": width,
            "stretch": stretch,
        }
        return ImageStreamWidget(widget_id, self.widget_name, props)

    def register_routes(self, fastapi_app: "FastAPI", app: "KApp") -> None:
        # widget_id -> the cancel signal for whichever /stream/ connection
        # is currently considered "the" viewer of that widget, only ever
        # populated in single_session mode (see below). One dict per KApp
        # (register_routes runs once at startup), so this never leaks
        # across separate app instances.
        active_streams: dict[str, asyncio.Event] = {}

        @fastapi_app.get("/stream/{widget_id}")
        async def mjpeg_stream(widget_id: str) -> StreamingResponse:
            widget = app.page.find(widget_id)
            if not isinstance(widget, ImageStreamWidget):
                raise HTTPException(status_code=404, detail="Stream not found")
            widget._ensure_provider_running()

            cancel: asyncio.Event | None = None
            if app.single_session:
                # The same "newest tab wins" policy already applied to the
                # WebSocket (see websocket.py's _supersede_existing_sessions),
                # applied independently here: in single_session mode at
                # most one browser is ever entitled to a given imagestream,
                # so a fresh connection for the same widget can only mean a
                # newer tab replacing an older one. Cutting the old
                # connection here, server-side, is what actually fixes the
                # "zombie tab keeps receiving frames" bug -- the frontend's
                # own supersede handling (see websocket.js/imagestream.js)
                # is a client-side best-effort on top of this, not a
                # substitute for it: it needs that tab's JS to run, and
                # under enough bandwidth the stream itself is exactly what
                # can stop any JS from running at all (see _mjpeg_chunks).
                previous = active_streams.get(widget_id)
                if previous is not None:
                    previous.set()
                cancel = asyncio.Event()
                active_streams[widget_id] = cancel

            async def body() -> AsyncIterator[bytes]:
                try:
                    async for chunk in _mjpeg_chunks(widget, cancel):
                        yield chunk
                finally:
                    # Only clear our own registration -- a newer connection
                    # may already have replaced it (it set `cancel` above,
                    # which is what got us here), and clearing that one's
                    # entry out from under it would let a third connection
                    # start without superseding anyone.
                    if cancel is not None and active_streams.get(widget_id) is cancel:
                        del active_streams[widget_id]

            return StreamingResponse(
                body(),
                media_type="multipart/x-mixed-replace; boundary=frame",
            )
