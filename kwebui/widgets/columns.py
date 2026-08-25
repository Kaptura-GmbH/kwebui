"""Columns widget: lay out widgets side by side, Streamlit ``st.columns`` style.

    left, right = app.columns(2)
    left.text("Left side")
    right.button("Click me", on_click=...)

    # or with explicit relative widths -- the list length is the column
    # count, and each number is that column's share of the row (must sum
    # to 1):
    narrow, medium, wide = app.columns([0.1, 0.2, 0.7])

A ``ColumnsWidget`` just holds ``n`` ``ColumnWidget`` children. Each column
is itself a generic container: it supports the same dynamic
``<column>.<widget_name>(...)`` sugar ``Empty`` uses to create widgets, but
*appends* every call instead of replacing a single slot -- unlike
``EmptyWidget``, a column can hold any number of widgets.

``create()`` never receives the ``KApp`` instance (only ``widget_id`` and
user args), so the columns can't get their ``_app`` reference wired at
creation time the way top-level widgets do. Instead ``_app`` is a property
on ``ColumnsWidget`` that cascades down to its children the moment
``KApp.__getattr__``'s factory sets it on the parent -- no core changes
needed for that to work.
"""

from __future__ import annotations

from typing import Any, Iterator, Sequence

from ..plugin import WidgetPlugin
from ..widget import Widget


class ColumnWidget(Widget):
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


class ColumnsWidget(Widget):
    """
    Example:
        left, right = app.columns(2)
        left.text("Left side")
        right.button("Click me", on_click=...)
    """

    def __getitem__(self, index: int) -> ColumnWidget:
        return self.children[index]

    def __iter__(self) -> Iterator[ColumnWidget]:
        return iter(self.children)

    def __len__(self) -> int:
        return len(self.children)

    @property
    def _app(self) -> Any:
        return self.__dict__.get("_app_ref")

    @_app.setter
    def _app(self, app: Any) -> None:
        self.__dict__["_app_ref"] = app
        for column in self.children:
            column._app = app
        if app is not None:
            app._on_widget_changed(self)


class ColumnPlugin(WidgetPlugin):
    widget_name = "column"

    def create(self, widget_id: str) -> ColumnWidget:
        return ColumnWidget(widget_id, self.widget_name, {})


_WEIGHT_SUM_TOLERANCE = 1e-6


class ColumnsPlugin(WidgetPlugin):
    """
    Example:
        left, right = app.columns(2)
        left.text("Left side")
        right.button("Click me", on_click=...)

        narrow, medium, wide = app.columns([0.1, 0.2, 0.7])
        narrow.text("10%")
        wide.text("70%")
    """

    widget_name = "columns"

    def create(self, widget_id: str, n: "int | Sequence[float]", *, gap: str = "1rem") -> ColumnsWidget:
        """``n`` is either a plain column count (equal-width columns, as
        before) or a list/tuple of relative widths -- one column per
        number, in that order, each getting that share of the row's
        width. The weights must sum to 1 (e.g. ``[0.1, 0.2, 0.7]`` for
        10%/20%/70%) and each be positive; anything else raises
        ``ValueError`` immediately rather than silently rendering a
        skewed or degenerate layout.

        Under the hood a weight just becomes that column's own CSS
        `flex-grow` (via `column.js`'s `flexStyle`, only set when a
        weight was actually given) -- `.sg-column`'s own `flex: 1` class
        rule is what already makes equal columns equal, so an
        `n: int` call is completely unaffected by this: none of its
        columns carry a `weight` prop at all, and the class rule alone
        governs them exactly as it always has.
        """
        if isinstance(n, int):
            columns = ColumnsWidget(widget_id, self.widget_name, {"gap": gap})
            columns.children = [ColumnWidget(f"{widget_id}-c{i}", "column", {}) for i in range(n)]
            return columns

        weights = list(n)
        if not weights:
            raise ValueError("columns() needs at least one weight in the list.")
        if any(w <= 0 for w in weights):
            raise ValueError(f"columns() weights must all be positive, got {weights!r}.")
        total = sum(weights)
        if abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
            raise ValueError(f"columns() weights must sum to 1, got {weights!r} (sum={total!r}).")

        columns = ColumnsWidget(widget_id, self.widget_name, {"gap": gap})
        columns.children = [
            ColumnWidget(f"{widget_id}-c{i}", "column", {"weight": weight})
            for i, weight in enumerate(weights)
        ]
        return columns
