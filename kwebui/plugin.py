"""The contract every widget plugin implements.

The core framework (``KApp``, ``Page``, ``Renderer``, the WebSocket layer)
only ever talks to widgets through this interface. It never imports a
concrete widget module by name -- see ``registry.py`` for how plugins are
discovered automatically from the ``widgets/`` package.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .events import Event
from .widget import Widget

if TYPE_CHECKING:
    from fastapi import FastAPI

    from .app import KApp


class WidgetPlugin:
    """Base class for a single widget type.

    Subclasses must set ``widget_name`` and implement ``create``. The
    other hooks have sensible defaults and only need overriding when a
    widget requires custom behaviour.
    """

    #: Unique name used as both the JSON "type" field and the dynamic
    #: ``app.<widget_name>(...)`` method name.
    widget_name: str = ""

    #: Extra names this plugin should also answer to, e.g. ``progress`` as
    #: an alias for ``progressbar`` when used inside an ``Empty`` slot.
    aliases: tuple[str, ...] = ()

    def create(self, widget_id: str, *args: Any, **kwargs: Any) -> Widget:
        """Build a new ``Widget`` instance from user-facing constructor args.

        This is the only required hook. It is called once per
        ``app.<widget_name>(...)`` (or ``slot.<widget_name>(...)``) call.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement create()")

    def handle_event(self, widget: Widget, event: Event) -> None:
        """React to a browser event addressed to this widget. Default: no-op."""

    def serialize(self, widget: Widget) -> dict[str, Any]:
        """Convert a widget to the JSON-safe dict sent to the frontend.

        Callables (event callbacks) and private keys (leading underscore,
        used for server-only bookkeeping such as local file paths) are
        stripped automatically -- plugins do not need to filter these
        themselves.
        """
        visible_props = {
            key: value
            for key, value in widget.props.items()
            if not callable(value) and not key.startswith("_")
        }
        return {
            "id": widget.id,
            "type": widget.widget_type,
            "props": visible_props,
            "style": self.default_style(),
            "highlighted": widget.highlighted,
            "highlight_color": widget.highlight_color,
            "visible": widget.visible,
            "enabled": widget.enabled,
        }

    def default_style(self) -> dict[str, str]:
        """Inline CSS defaults (camelCase JS style keys) applied before mount."""
        return {}

    def register_routes(self, fastapi_app: "FastAPI", app: "KApp") -> None:
        """Optional hook: mount extra HTTP routes this widget type needs.

        Used by widgets like ``image`` and ``imagestream`` that must serve
        binary data (files, MJPEG streams) outside the WebSocket channel.
        Default: no extra routes.
        """
