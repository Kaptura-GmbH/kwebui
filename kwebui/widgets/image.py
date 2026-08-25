"""Image widget: a static image from a local file or a URL.

Local files are served through a `/media/{widget_id}` route that this
plugin mounts itself via `register_routes` -- the core router never has
to know images exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from ..plugin import WidgetPlugin
from ..widget import Widget

if TYPE_CHECKING:
    from ..app import KApp


class ImageWidget(Widget):
    def set_source(self, source: str) -> "ImageWidget":
        """Point the image at a new local path or URL."""
        props = _resolve_source(self.id, source)
        self.update(**props)
        return self

    def set_width(self, width: float) -> "ImageWidget":
        """Resize the image viewer. -1 or 0 falls back to the image's own
        size. Ignored while ``stretch`` is True."""
        self.update(width=width)
        return self

    def set_stretch(self, stretch: bool) -> "ImageWidget":
        """Toggle whether the viewer fills its parent container's width."""
        self.update(stretch=stretch)
        return self


def _resolve_source(widget_id: str, source: str) -> dict:
    if source.startswith(("http://", "https://")):
        return {"src": source, "_local_path": None}
    return {"src": f"/media/{widget_id}", "_local_path": str(Path(source).resolve())}


class ImagePlugin(WidgetPlugin):
    """
    Example:
        app.image("cat.jpg", width=300)
        app.image("cat.jpg", stretch=True)   # fills the parent container's width
        app.image("https://example.com/cat.jpg")
    """

    widget_name = "image"

    def create(self, widget_id: str, source: str, *, width: float = -1, stretch: bool = False) -> ImageWidget:
        props = {"width": width, "stretch": stretch, **_resolve_source(widget_id, source)}
        return ImageWidget(widget_id, self.widget_name, props)

    def register_routes(self, fastapi_app: "FastAPI", app: "KApp") -> None:
        @fastapi_app.get("/media/{widget_id}")
        async def serve_media(widget_id: str) -> FileResponse:
            widget = app.page.find(widget_id)
            local_path = widget.props.get("_local_path") if widget else None
            if not local_path or not Path(local_path).is_file():
                raise HTTPException(status_code=404, detail="Image not found")
            return FileResponse(local_path)
