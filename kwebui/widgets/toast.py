"""Toast widget: a transient corner notification, Streamlit ``st.toast`` style.

The browser removes the notification from the DOM on its own after
``duration_ms`` -- the Python side never hears about it and the widget
stays in the page tree. That's harmless for the sessions it was broadcast
to (they already saw and dismissed it), but a session that connects later
will replay it, briefly, on init. This is the same shared-tree trade-off
``decisions.md`` documents for the rest of kwebui, not something specific
to toasts.
"""

from __future__ import annotations

from ..plugin import WidgetPlugin
from ..widget import Widget

_ICONS = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "🚫", "plain": ""}


class ToastWidget(Widget):
    """
    A toast only matters if it's created *from* a callback -- see
    ``AlertWidget`` in ``alert.py`` for why the ``_app`` property below is
    needed to make ``self.toast(...)`` broadcast immediately instead of
    silently waiting for the next full page load.
    """

    @property
    def _app(self):
        return self.__dict__.get("_app_ref")

    @_app.setter
    def _app(self, app):
        self.__dict__["_app_ref"] = app
        if app is not None:
            app._on_widget_changed(self)


class ToastPlugin(WidgetPlugin):
    """
    Example:
        app.toast("Saved!", level="success")
    """

    widget_name = "toast"

    def create(
        self,
        widget_id: str,
        message: str,
        *,
        icon: str | None = None,
        level: str = "info",
        duration_ms: int = 4000,
    ) -> ToastWidget:
        props = {
            "message": message,
            "icon": _ICONS.get(level, "") if icon is None else icon,
            "level": level,
            "duration_ms": duration_ms,
        }
        return ToastWidget(widget_id, self.widget_name, props)
