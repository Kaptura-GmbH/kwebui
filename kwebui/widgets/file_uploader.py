"""FileUploader widget: upload one or more files from the browser.

Uploaded bytes arrive through a dedicated HTTP POST route
(``register_routes``) rather than the WebSocket event channel -- binary
payloads don't belong in JSON messages, the same reasoning that keeps
``image`` and ``imagestream`` off the WebSocket too. Because the upload
lands outside ``KApp._dispatch_event``, ``on_upload`` runs with
``app.session`` unset, exactly like the image/imagestream routes.

Parsing a multipart upload requires the optional ``python-multipart``
package (``pip install kwebui[file_uploader]``) -- it is *not* a core
kwebui dependency, since every other widget works without it. The route
below deliberately takes the raw ``Request`` rather than declaring a
typed ``files: list[UploadFile] = File(...)`` parameter, because that
typed-parameter form makes FastAPI attempt the multipart parse as part of
its own dependency resolution, before our handler body ever runs -- if
the package is missing, that raises deep inside FastAPI/Starlette instead
of giving the caller a clean, actionable JSON error. Probing for the
package ourselves first (mirroring the exact fallback Starlette's own
form parser uses, see ``starlette/formparsers.py``) lets us return that
error instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from fastapi import FastAPI, Request
from starlette.datastructures import UploadFile

from ..plugin import WidgetPlugin
from ..widget import Widget

if TYPE_CHECKING:
    from ..app import KApp

INSTALL_HINT = "File uploads require the 'python-multipart' package. Install it with: pip install kwebui[file_uploader]"


def _multipart_available() -> bool:
    try:
        import python_multipart  # noqa: F401
    except ModuleNotFoundError:
        try:
            import multipart  # noqa: F401
        except ModuleNotFoundError:
            return False
    return True


class FileUploaderWidget(Widget):
    @property
    def filenames(self) -> list[str]:
        return list(self.props.get("filenames", []))


class FileUploaderPlugin(WidgetPlugin):
    """
    Example:
        app.file_uploader("Upload a CSV", accept=".csv", on_upload=handle_csv)

        def handle_csv(filename: str, data: bytes) -> None:
            ...
    """

    widget_name = "file_uploader"

    def create(
        self,
        widget_id: str,
        label: str = "",
        *,
        accept: str = "",
        multiple: bool = False,
        on_upload: Callable[[str, bytes], None] | None = None,
    ) -> FileUploaderWidget:
        props = {
            "label": label,
            "accept": accept,
            "multiple": multiple,
            "on_upload": on_upload,
            "filenames": [],
        }
        return FileUploaderWidget(widget_id, self.widget_name, props)

    def register_routes(self, fastapi_app: "FastAPI", app: "KApp") -> None:
        @fastapi_app.post("/upload/{widget_id}")
        async def upload(widget_id: str, request: Request) -> dict:
            if not _multipart_available():
                return {"ok": False, "error": INSTALL_HINT}

            widget = app.page.find(widget_id)
            if not isinstance(widget, FileUploaderWidget):
                return {"ok": False, "error": "unknown widget"}

            form = await request.form()
            uploaded_files = [value for value in form.getlist("files") if isinstance(value, UploadFile)]

            callback = widget.props.get("on_upload")
            filenames = []
            for uploaded in uploaded_files:
                data = await uploaded.read()
                filenames.append(uploaded.filename)
                if callback is not None:
                    callback(uploaded.filename, data)

            widget.update(filenames=filenames)
            return {"ok": True, "filenames": filenames}
