"""Live viewer for Daheng industrial cameras (gxipy SDK). Run with:

    # gxipy is a vendor SDK, not on PyPI -- install it from the Daheng
    # driver package, then downgrade numpy: gxipy's DeviceManager still
    # imports the removed `numpy.compat.long` shim, so it needs numpy<2.
    pip install /path/to/Galaxy_Linux_Python_.../api
    pip install -e ".[imagestream]" "numpy<2"
    python examples/daheng_demo.py

Then open the printed URL (default http://127.0.0.1:8701, or the next
free port after it) in a browser: pick a camera from the
list, watch its live feed, and adjust exposure/gain to see the effect
on the stream in real time. The FPS field takes effect immediately
(no restart) -- set it to 0 for unthrottled/max-speed capture. On this
machine's cameras at full 1440x1080 resolution, grab+convert+JPEG-encode
alone sustains ~140-190 fps depending on JPEG quality; actual delivered
fps is also capped by the camera's own AcquisitionFrameRate and by
network/USB bandwidth for the encoded frame size, so the JPEG quality
field is there too -- it trades image quality for both encode speed and
frame size.
"""

from __future__ import annotations

import threading
import time

import cv2
import gxipy as gx
import numpy as np

from kwebui import KApp

_GET_IMAGE_TIMEOUT_MS = 200
# How often _next_frame() may retry opening a camera that just failed a
# grab. _next_frame() runs at the stream's fps (40/sec by default), so
# without this a genuinely unplugged camera would get hammered with
# open_device_by_sn() calls dozens of times a second instead of just
# waiting for it to come back.
_RECONNECT_INTERVAL_S = 2.0
# How often _next_frame() may re-scan for connected/disconnected cameras
# to keep the listbox in sync. Same reasoning as _RECONNECT_INTERVAL_S --
# _next_frame() runs at the stream's fps, so this needs its own,
# independent cooldown rather than scanning on every tick.
_DEVICE_LIST_REFRESH_INTERVAL_S = 2.0


def _frame_to_bgr(cam, raw_image) -> np.ndarray | None:
    """Convert a raw acquired image to an OpenCV-compatible BGR array."""
    if cam.PixelColorFilter.is_implemented():
        rgb_image = raw_image.convert("RGB")
        if rgb_image is None:
            return None
        numpy_image = rgb_image.get_numpy_array()
        if numpy_image is None:
            return None
        return cv2.cvtColor(numpy_image, cv2.COLOR_RGB2BGR)

    numpy_image = raw_image.get_numpy_array()
    if numpy_image is None:
        return None
    return cv2.cvtColor(numpy_image, cv2.COLOR_GRAY2BGR)


def _text_frame(message: str) -> np.ndarray:
    frame = np.full((240, 320, 3), (24, 24, 24), dtype=np.uint8)
    cv2.putText(frame, message, (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1, cv2.LINE_AA)
    return frame


def _encode_jpeg(frame: np.ndarray, quality: int = 85) -> bytes:
    ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return jpeg.tobytes() if ok else b""


class DahengDemo(KApp):
    def build(self) -> None:
        self.text("Daheng Camera Viewer", size=28, bold=True)

        # DeviceManager de-initializes the underlying camera API library
        # once its last reference is garbage collected, so it must stay
        # alive (as an attribute on self) for as long as any camera opened
        # from it is still in use.
        self._device_manager = gx.DeviceManager()
        _, devices = self._device_manager.update_device_list()
        self._label_to_sn = {d["display_name"]: d["sn"] for d in devices}
        self._devices_by_sn = {d["sn"]: d for d in devices}

        self._cam_lock = threading.Lock()
        self._active_cam = None
        self._active_sn: str | None = None
        self._jpeg_quality = 85
        self._last_reconnect_attempt = 0.0
        self._last_device_list_refresh = 0.0

        if not devices:
            self.text("No Daheng camera found.", color="#dc2626")
            return

        self.status = self.empty()
        self.status.text("Select a camera to begin.", color="#6b7280")

        self.camera_list = self.listbox(list(self._label_to_sn), on_select=self.on_select_camera)
        self.start_button = self.button(
            "Start / Reconnect camera", on_click=lambda: self.on_start_button()
        )

        self.stream = self.imagestream(frame_provider=self._next_frame, fps=40 )

        self.fps_edit = self.textedit(
            "Stream FPS (0 = max speed)", placeholder="40", on_change=self.on_fps_change
        )
        self.quality_edit = self.textedit(
            "JPEG quality (1-100)", placeholder="85", on_change=self.on_quality_change
        )

        self.exposure_edit = self.textedit(
            "Exposure time (us)", placeholder="e.g. 5000", on_change=self.on_exposure_change
        )
        self.auto_exposure = self.checkbox("Auto exposure", on_change=self.on_auto_exposure_change)

        self.gain_edit = self.textedit("Gain (dB)", placeholder="e.g. 0", on_change=self.on_gain_change)
        self.auto_gain = self.checkbox("Auto gain", on_change=self.on_auto_gain_change)

    # -- camera lifecycle -----------------------------------------------

    def on_select_camera(self, label: str) -> None:
        sn = self._label_to_sn[label]
        if sn == self._active_sn:
            return
        self._activate_camera(sn, label)

    def on_start_button(self) -> None:
        """Manually (re)activate whichever camera is highlighted in the
        listbox. Two automatic mechanisms already cover the common cases
        -- the listbox's mount-time announce (see listbox.js) auto-selects
        and streams the first camera as soon as a fresh page loads, and
        _next_frame()'s auto-reconnect retries a disconnected camera every
        ~2s on its own -- this button exists as a guaranteed, immediate,
        cache-independent fallback: it forces the same activation those
        rely on, for whenever a page loaded with stale/cached frontend
        assets before the listbox fix, or the user doesn't want to wait
        out the automatic retry interval."""
        label = self.camera_list.selected_item
        if label is None:
            # Nothing selected yet (e.g. the listbox's own mount-time
            # announce didn't fire) -- default to the first camera, same
            # as what the listbox visually shows selected by default.
            label = next(iter(self._label_to_sn), None)
        if label is None:
            return
        self._activate_camera(self._label_to_sn[label], label)

    def _activate_camera(self, sn: str, label: str) -> None:
        with self._cam_lock:
            self._close_active_camera()
            # _active_sn is the user's *intended* camera, set unconditionally
            # here -- independent of whether _open_camera_locked below
            # actually succeeds. _next_frame()'s auto-reconnect needs this
            # to know which camera to keep retrying even while it's not
            # currently open (see _active_cam's docstring note).
            self._active_sn = sn
            self._last_reconnect_attempt = 0.0
            error = self._open_camera_locked(sn)

        if error is not None:
            self.status.text(f"Could not open {label}: {error}", color="#dc2626")
            return
        self._sync_config_widgets(self._active_cam)
        self.status.text(f"Streaming {label}", color="#2563eb")

    def _open_camera_locked(self, sn: str) -> str | None:
        """Open and configure the camera at ``sn``, making it
        ``self._active_cam`` on success. Must be called with
        ``self._cam_lock`` already held (by ``on_select_camera`` or
        ``_next_frame``'s auto-reconnect) and with ``self._active_sn``
        already set to ``sn`` by the caller. Returns ``None`` on success,
        or the underlying exception's message on failure (surfaced in the
        status text -- these SDK errors are exactly what's needed to tell
        a plain timeout apart from e.g. a stale exclusive-access lock).
        ``self._active_cam`` is left as ``None`` on failure so a later
        call -- e.g. the next auto-reconnect tick -- can simply retry."""
        try:
            self._device_manager.update_device_list()
            cam = self._device_manager.open_device_by_sn(sn)
            cam.TriggerMode.set(gx.GxSwitchEntry.OFF)
            cam.stream_on()
        except Exception as exc:
            return str(exc) or type(exc).__name__
        self._active_cam = cam
        return None

    def _close_active_camera(self) -> None:
        if self._active_cam is None:
            return
        cam = self._active_cam
        # stream_off() and close_device() get separate try/except blocks
        # on purpose: if the device is already gone (physically
        # unplugged), stream_off() raising must not skip close_device()
        # -- close_device() is what releases the SDK's exclusive-access
        # handle, and skipping it would leave that handle "held" forever,
        # so every future open_device_by_sn() for this camera keeps
        # failing even once it's physically reconnected.
        try:
            cam.stream_off()
        except Exception:
            pass
        try:
            cam.close_device()
        except Exception:
            # The device may already be gone (physically unplugged) -- a
            # failed close must never block opening a different camera, or
            # reconnecting to this same one once it's replugged.
            pass
        finally:
            self._active_cam = None
            # _active_sn is deliberately left alone here -- it's the
            # camera the user wants streaming, not just the one that
            # happens to be open right now. Clearing it would make
            # _next_frame() fall back to the plain "Select a camera"
            # placeholder and stop retrying after a single failed
            # reconnect attempt, instead of continuing to retry
            # automatically until the camera comes back.

    def _sync_config_widgets(self, cam) -> None:
        if cam.ExposureTime.is_readable():
            self.exposure_edit.set_value(f"{cam.ExposureTime.get():.0f}")
        if cam.ExposureAuto.is_implemented():
            self.auto_exposure.set_checked(cam.ExposureAuto.get()[0] == gx.GxAutoEntry.CONTINUOUS)
        if cam.Gain.is_readable():
            self.gain_edit.set_value(f"{cam.Gain.get():.1f}")
        if cam.GainAuto.is_implemented():
            self.auto_gain.set_checked(cam.GainAuto.get()[0] == gx.GxAutoEntry.CONTINUOUS)

    # -- live stream ------------------------------------------------------

    def _next_frame(self) -> bytes:
        with self._cam_lock:
            self._refresh_device_list_locked()
            sn = self._active_sn
            if sn is None:
                return _encode_jpeg(_text_frame("Select a camera"))
            cam = self._active_cam
            if cam is None:
                # A camera is selected but not currently open -- a previous
                # (re)connect attempt failed. Keep retrying via sn rather
                # than falling back to the "no camera selected" placeholder.
                self._maybe_reconnect_locked(sn)
                return b""
            try:
                raw_image = cam.data_stream[0].get_image(_GET_IMAGE_TIMEOUT_MS)
            except Exception:
                raw_image = None
            if raw_image is None:
                self._maybe_reconnect_locked(sn)
                return b""
            frame = _frame_to_bgr(cam, raw_image)
        return _encode_jpeg(frame, self._jpeg_quality) if frame is not None else b""

    def _maybe_reconnect_locked(self, sn: str) -> None:
        """Called from ``_next_frame`` (with ``self._cam_lock`` already
        held) whenever a frame grab fails -- covers both a plain transient
        timeout and the active camera having been physically unplugged.
        Retries opening it fresh, but at most once every
        ``_RECONNECT_INTERVAL_S`` to avoid hammering a genuinely
        disconnected camera on every poll tick. Fully automatic: no user
        action needed for the stream to recover once the camera is back."""
        now = time.monotonic()
        if now - self._last_reconnect_attempt < _RECONNECT_INTERVAL_S:
            return
        self._last_reconnect_attempt = now
        self._close_active_camera()
        device = self._devices_by_sn.get(sn)
        label = device["display_name"] if device else sn
        error = self._open_camera_locked(sn)
        if error is None:
            self.status.text(f"Reconnected to {label}", color="#2563eb")
        else:
            self.status.text(f"{label} disconnected -- retrying... ({error})", color="#dc2626")

    def _refresh_device_list_locked(self) -> None:
        """Called from ``_next_frame`` (with ``self._cam_lock`` already
        held) on every tick, but only actually re-scans at most once every
        ``_DEVICE_LIST_REFRESH_INTERVAL_S`` -- keeps the listbox in sync
        with cameras being plugged in or unplugged, instead of the
        snapshot frozen at app startup. Piggybacks on the same
        already-running poll loop as ``_maybe_reconnect_locked`` rather
        than a dedicated thread, since kwebui has no periodic-callback
        primitive of its own and this is already called at a steady rate."""
        now = time.monotonic()
        if now - self._last_device_list_refresh < _DEVICE_LIST_REFRESH_INTERVAL_S:
            return
        self._last_device_list_refresh = now
        try:
            _, devices = self._device_manager.update_device_list()
        except Exception:
            return  # SDK hiccup -- try again next interval
        label_to_sn = {d["display_name"]: d["sn"] for d in devices}
        if label_to_sn == self._label_to_sn:
            return
        self._label_to_sn = label_to_sn
        self._devices_by_sn = {d["sn"]: d for d in devices}
        self.camera_list.set_items(list(label_to_sn))
        # Re-sync the listbox's visual selection to wherever the actually
        # active camera (by serial number, not position) now sits in the
        # refreshed list -- set_items() alone doesn't touch selected_index,
        # so a camera further down the list disappearing would otherwise
        # leave the listbox highlighting the wrong item by leftover index.
        active_label = next((l for l, s in label_to_sn.items() if s == self._active_sn), None)
        self.camera_list.set_selected_index(
            list(label_to_sn).index(active_label) if active_label is not None else None
        )

    # -- stream settings ---------------------------------------------------

    def on_fps_change(self, value: str) -> None:
        try:
            fps = float(value)
        except ValueError:
            return
        self.stream.set_fps(fps if fps > 0 else None)
        self.status.text(
            "Stream set to max speed (unthrottled)" if fps <= 0 else f"Stream FPS set to {fps:.0f}",
            color="#2563eb",
        )

    def on_quality_change(self, value: str) -> None:
        try:
            quality = int(float(value))
        except ValueError:
            return
        self._jpeg_quality = max(1, min(100, quality))
        self.status.text(f"JPEG quality set to {self._jpeg_quality}", color="#2563eb")

    # -- config callbacks -------------------------------------------------

    def on_exposure_change(self, value: str) -> None:
        cam = self._active_cam
        if cam is None:
            return
        try:
            microseconds = float(value)
        except ValueError:
            return
        # Cameras generally refuse manual writes while auto mode owns the
        # feature, so ExposureAuto must be turned off *before* checking
        # is_writable() -- checking it first made this a silent no-op
        # whenever auto exposure was on.
        if cam.ExposureAuto.is_implemented():
            cam.ExposureAuto.set(gx.GxAutoEntry.OFF)
            self.auto_exposure.set_checked(False)
        if not cam.ExposureTime.is_writable():
            return
        exposure_range = cam.ExposureTime.get_range()
        clamped = min(max(microseconds, exposure_range["min"]), exposure_range["max"])
        cam.ExposureTime.set(clamped)
        self.status.text(f"Exposure set to {clamped:.0f} us", color="#2563eb")

    def on_auto_exposure_change(self, checked: bool) -> None:
        cam = self._active_cam
        if cam is None or not cam.ExposureAuto.is_implemented():
            return
        cam.ExposureAuto.set(gx.GxAutoEntry.CONTINUOUS if checked else gx.GxAutoEntry.OFF)
        self.status.text("Auto exposure " + ("enabled" if checked else "disabled"), color="#2563eb")

    def on_gain_change(self, value: str) -> None:
        cam = self._active_cam
        if cam is None:
            return
        try:
            gain_db = float(value)
        except ValueError:
            return
        # Same ordering requirement as exposure: GainAuto must be turned
        # off before Gain becomes writable.
        if cam.GainAuto.is_implemented():
            cam.GainAuto.set(gx.GxAutoEntry.OFF)
            self.auto_gain.set_checked(False)
        if not cam.Gain.is_writable():
            return
        gain_range = cam.Gain.get_range()
        clamped = min(max(gain_db, gain_range["min"]), gain_range["max"])
        cam.Gain.set(clamped)
        self.status.text(f"Gain set to {clamped:.1f} dB", color="#2563eb")

    def on_auto_gain_change(self, checked: bool) -> None:
        cam = self._active_cam
        if cam is None or not cam.GainAuto.is_implemented():
            return
        cam.GainAuto.set(gx.GxAutoEntry.CONTINUOUS if checked else gx.GxAutoEntry.OFF)
        self.status.text("Auto gain " + ("enabled" if checked else "disabled"), color="#2563eb")


if __name__ == "__main__":
    DahengDemo(title="Daheng Camera Viewer").run()
