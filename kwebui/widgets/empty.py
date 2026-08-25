"""Empty widget: a placeholder slot whose contents can be replaced in place.

Equivalent to Streamlit's ``st.empty()``. Structurally this is just a
widget that holds exactly one child (``Widget.children`` already supports
that in the core) -- the only thing this plugin adds is the dynamic
``slot.<widget_name>(...)`` sugar for filling the slot.
"""

from __future__ import annotations

from typing import Any

from ..plugin import WidgetPlugin
from ..widget import Widget


class EmptyWidget(Widget):
    """
    Example:
        slot = app.empty()
        slot.text("Loading...")
        ...
        slot.progressbar(100)   # replaces the text with a progress bar
    """

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        app = self.__dict__.get("_app")
        if app is None or name not in app.registry.names():
            raise AttributeError(name)

        def factory(*args: Any, **kwargs: Any) -> Widget:
            child = app.registry.get(name).create(app._next_id(), *args, **kwargs)
            # Parent the child into the slot (and broadcast that) before
            # wiring up its `_app`. Widgets that self-broadcast on `_app`
            # assignment (alert, toast, popup -- see AlertWidget) would
            # otherwise fire an update for an unparented widget, which the
            # frontend has no choice but to mount as a spurious top-level
            # node since it doesn't know yet that the widget belongs in
            # this slot. Once the slot's own broadcast has already told the
            # frontend about the nested child, that second update patches
            # it in place instead of duplicating it.
            self.set(child)
            child._app = app
            return child

        return factory

    def set(self, child: Widget) -> Widget:
        """Replace this slot's content with an already-built widget."""
        child.slot_of = self.id
        self.children = [child]
        if self._app is not None:
            self._app._on_widget_changed(self)
        return child

    def clear(self) -> None:
        self.children = []
        if self._app is not None:
            self._app._on_widget_changed(self)


class EmptyPlugin(WidgetPlugin):
    widget_name = "empty"

    def create(self, widget_id: str) -> EmptyWidget:
        return EmptyWidget(widget_id, self.widget_name, {})
