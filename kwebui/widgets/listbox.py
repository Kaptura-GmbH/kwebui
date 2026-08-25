"""ListBox widget: pick one item from a list of strings."""

from __future__ import annotations

from typing import Callable, Sequence

from ..events import Event
from ..plugin import WidgetPlugin
from ..widget import Widget


class ListBoxWidget(Widget):
    @property
    def selected_index(self) -> int | None:
        return self.props.get("selected_index")

    @property
    def selected_item(self) -> str | None:
        index = self.selected_index
        items = self.props.get("items", [])
        return items[index] if index is not None and 0 <= index < len(items) else None

    def set_items(self, items: Sequence[str]) -> "ListBoxWidget":
        self.update(items=list(items))
        return self

    def set_selected_index(self, index: int | None) -> "ListBoxWidget":
        self.update(selected_index=index)
        return self


class ListBoxPlugin(WidgetPlugin):
    """
    Example:
        app.listbox(["Apples", "Bananas", "Cherries"], on_select=lambda item: print(item))
    """

    widget_name = "listbox"

    def create(
        self,
        widget_id: str,
        items: Sequence[str],
        *,
        selected_index: int | None = None,
        on_select: Callable[[str], None] | None = None,
    ) -> ListBoxWidget:
        props = {"items": list(items), "selected_index": selected_index, "on_select": on_select}
        return ListBoxWidget(widget_id, self.widget_name, props)

    def handle_event(self, widget: Widget, event: Event) -> None:
        if event.type == "select":
            index = int(event.payload.get("index", -1))
            items: list[str] = widget.props.get("items", [])
            if 0 <= index < len(items):
                widget.update(selected_index=index)
                callback = widget.props.get("on_select")
                if callback is not None:
                    callback(items[index])
