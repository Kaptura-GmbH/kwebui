"""Status banners, Streamlit ``st.success``/``st.info``/``st.warning``/``st.error`` style.

Four call names, four plugins, one shared ``AlertWidget`` shape -- each
plugin only differs in ``widget_name`` and icon, so there's nothing to
gain from a shared base class (and a ``WidgetPlugin`` subclass living in
this module would get auto-registered by ``registry.discover()`` too,
under its own -- wrong -- name).
"""

from __future__ import annotations

from ..plugin import WidgetPlugin
from ..widget import Widget

_ICONS = {"success": "✅", "info": "ℹ️", "warning": "⚠️", "error": "🚫"}


class AlertWidget(Widget):
    """
    Success/info/warning/error banners exist to be created *from* a
    callback (``if clicked: self.success("Saved!")``) rather than only
    upfront in ``build()``. ``KApp.__getattr__``'s factory only appends a
    freshly created widget to the page -- it never broadcasts, since for
    every other widget type the assumption is "declared once in build(),
    mutated afterwards via update()". Overriding the ``_app`` setter lets
    an ``AlertWidget`` push itself out the moment it's wired to the app,
    which is exactly when ``KApp.__getattr__`` assigns it -- no core
    changes required. Before the server starts serving, ``_on_widget_changed``
    is a no-op (no sessions, no loop yet), so this is free during ``build()``.
    """

    def set_text(self, text: str) -> "AlertWidget":
        self.update(text=text)
        return self

    @property
    def _app(self):
        return self.__dict__.get("_app_ref")

    @_app.setter
    def _app(self, app):
        self.__dict__["_app_ref"] = app
        if app is not None:
            app._on_widget_changed(self)


def _create_alert(widget_id: str, level: str, text: str) -> AlertWidget:
    props = {"text": text, "level": level, "icon": _ICONS[level]}
    return AlertWidget(widget_id, level, props)


class SuccessPlugin(WidgetPlugin):
    """Example: app.success("Saved successfully!")"""

    widget_name = "success"

    def create(self, widget_id: str, text: str) -> AlertWidget:
        return _create_alert(widget_id, self.widget_name, text)


class InfoPlugin(WidgetPlugin):
    """Example: app.info("Heads up: this is informational.")"""

    widget_name = "info"

    def create(self, widget_id: str, text: str) -> AlertWidget:
        return _create_alert(widget_id, self.widget_name, text)


class WarningPlugin(WidgetPlugin):
    """Example: app.warning("This action can't be undone.")"""

    widget_name = "warning"

    def create(self, widget_id: str, text: str) -> AlertWidget:
        return _create_alert(widget_id, self.widget_name, text)


class ErrorPlugin(WidgetPlugin):
    """Example: app.error("Something went wrong.")"""

    widget_name = "error"

    def create(self, widget_id: str, text: str) -> AlertWidget:
        return _create_alert(widget_id, self.widget_name, text)
