"""Topbar widget: a full-width panel pinned to the top of the page.

    bar = app.topbar()
    bar.workflow_tracker(tasks)

Structurally just another append-only container -- the same idea as
``ColumnWidget``/``SidebarWidget`` in ``columns.py``/``sidebar.py``. What
makes it a "topbar" rather than a plain column is entirely in
``topbar.js``: full-bleed width (breaking out of ``#app-root``'s centered
``max-width``) and, optionally, ``position: sticky`` to stay visible
while the page scrolls -- not anything the Python side needs to know
about beyond the ``sticky`` flag.
"""

from __future__ import annotations

from typing import Any

from ..plugin import WidgetPlugin
from ..widget import Widget


class TopbarWidget(Widget):
    """
    Example:
        bar = app.topbar()
        bar.text("My App", bold=True)
        bar.workflow_tracker(tasks)

    Also usable as a context manager, mirroring ``SidebarWidget``:

        with app.topbar() as bar:
            bar.workflow_tracker(tasks)
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

    def __enter__(self) -> "TopbarWidget":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class TopbarPlugin(WidgetPlugin):
    """
    Example:
        bar = app.topbar()
        bar.workflow_tracker(tasks)

        pinned = app.topbar(sticky=False)  # scrolls away with the page instead
    """

    widget_name = "topbar"

    def create(self, widget_id: str, *, sticky: bool = True) -> TopbarWidget:
        return TopbarWidget(widget_id, self.widget_name, {"sticky": sticky})
