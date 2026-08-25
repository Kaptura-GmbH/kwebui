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

import cv2
import gxipy as gx
import numpy as np

from kwebui import KApp

_GET_IMAGE_TIMEOUT_MS = 200


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

        if not devices:
            self.text("No Daheng camera found.", color="#dc2626")
            return

        self.status = self.empty()
        self.status.text("Select a camera to begin.", color="#6b7280")

        self.camera_list = self.listbox(list(self._label_to_sn), on_select=self.on_select_camera)

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
        with self._cam_lock:
            self._close_active_camera()
            cam = self._device_manager.open_device_by_sn(sn)
            cam.TriggerMode.set(gx.GxSwitchEntry.OFF)
            cam.stream_on()
            self._active_cam = cam
            self._active_sn = sn

        self._sync_config_widgets(cam)
        device = self._devices_by_sn[sn]
        self.status.text(f"Streaming {device['display_name']}", color="#2563eb")

    def _close_active_camera(self) -> None:
        if self._active_cam is not None:
            self._active_cam.stream_off()
            self._active_cam.close_device()
            self._active_cam = None
            self._active_sn = None

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
            cam = self._active_cam
            if cam is None:
                return _encode_jpeg(_text_frame("Select a camera"))
            raw_image = cam.data_stream[0].get_image(_GET_IMAGE_TIMEOUT_MS)
            frame = _frame_to_bgr(cam, raw_image) if raw_image is not None else None
        return _encode_jpeg(frame, self._jpeg_quality) if frame is not None else b""

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
