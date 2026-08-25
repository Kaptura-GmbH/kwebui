"""Sidebar widget: a persistent, collapsible side panel, Streamlit ``st.sidebar`` style.

    sidebar = app.sidebar()
    sidebar.text("Navigation", bold=True)
    sidebar.button("Home", on_click=go_home)

Structurally this is just another append-only container -- the same idea
as ``ColumnWidget`` in ``columns.py``. What makes it a "sidebar" rather
than a lone column is entirely in ``sidebar.js``: fixed, full-height
positioning and a collapse toggle, not anything the Python side needs to
know about.
"""

from __future__ import annotations

from typing import Any

from ..plugin import WidgetPlugin
from ..widget import Widget


class SidebarWidget(Widget):
    """
    Example:
        sidebar = app.sidebar()
        sidebar.text("Navigation", bold=True)
        sidebar.button("Home", on_click=go_home)

    Also usable as a context manager, mirroring ``with st.sidebar:``:

        with app.sidebar() as sidebar:
            sidebar.text("Navigation", bold=True)

    A typical app creates one sidebar (in ``build()``) and keeps the
    returned handle around -- nothing stops you from calling
    ``app.sidebar()`` more than once, but you'll get two overlapping
    fixed panels, since kwebui has no notion of a singleton widget.
    """

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        app = self.__dict__.get("_app")
        if app is None or name not in app.registry.names():
            raise AttributeError(name)

        def factory(*args: Any, **kwargs: Any) -> Widget:
            child = app.registry.get(name).create(app._next_id(), *args, **kwargs)
            # Parent+broadcast before wiring up `_app` -- see EmptyWidget's
            # factory for why the order matters (self-broadcasting widgets
            # like alert/toast/popup/columns would otherwise announce
            # themselves unparented first and get mounted twice).
            self.children.append(child)
            if self._app is not None:
                self._app._on_widget_changed(self)
            child._app = app
            return child

        return factory

    def __enter__(self) -> "SidebarWidget":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class SidebarPlugin(WidgetPlugin):
    """
    Example:
        sidebar = app.sidebar()
        sidebar.text("Navigation", bold=True)

        pinned = app.sidebar(collapsible=False)  # no collapse toggle at all
    """

    widget_name = "sidebar"

    def create(self, widget_id: str, *, collapsible: bool = True) -> SidebarWidget:
        return SidebarWidget(widget_id, self.widget_name, {"collapsible": collapsible})
