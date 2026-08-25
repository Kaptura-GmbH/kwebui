"""The UI tree: an ordered list of top-level widgets."""

from __future__ import annotations

from .widget import Widget


class Page:
    """Holds the top-level widgets that make up the whole application."""

    def __init__(self) -> None:
        self.children: list[Widget] = []

    def add(self, widget: Widget) -> None:
        self.children.append(widget)

    def find(self, widget_id: str) -> Widget | None:
        """Depth-first search for a widget by id, including slot children."""
        return _find(self.children, widget_id)

    def remove(self, widget_id: str) -> bool:
        """Remove a widget by id, wherever it is in the tree. Returns whether
        it was found. Used for one-shot widgets like an answered popup, so a
        browser that connects later doesn't see it "replay" on init."""
        return _remove(self.children, widget_id)


def _find(widgets: list[Widget], widget_id: str) -> Widget | None:
    for widget in widgets:
        if widget.id == widget_id:
            return widget
        found = _find(widget.children, widget_id)
        if found is not None:
            return found
    return None


def _remove(widgets: list[Widget], widget_id: str) -> bool:
    for index, widget in enumerate(widgets):
        if widget.id == widget_id:
            del widgets[index]
            return True
        if _remove(widget.children, widget_id):
            return True
    return False
