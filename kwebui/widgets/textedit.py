"""TextEdit widget: a single-line or multi-line text input."""

from __future__ import annotations

from typing import Callable

from ..events import Event
from ..plugin import WidgetPlugin
from ..widget import Widget


class TextEditWidget(Widget):
    @property
    def value(self) -> str:
        return str(self.props.get("value", ""))

    def set_value(self, value: str) -> "TextEditWidget":
        self.update(value=value)
        return self


class TextEditPlugin(WidgetPlugin):
    """
    Example:
        app.textedit("Name", placeholder="Jane Doe", on_change=lambda v: print(v))
        app.textedit("Device ID", on_enter=lambda v: check_inventory(v))
    """

    widget_name = "textedit"

    def create(
        self,
        widget_id: str,
        label: str = "",
        *,
        value: str = "",
        placeholder: str = "",
        multiline: bool = False,
        password: bool = False,
        on_change: Callable[[str], None] | None = None,
        on_enter: Callable[[str], None] | None = None,
    ) -> TextEditWidget:
        props = {
            "label": label,
            "value": value,
            "placeholder": placeholder,
            "multiline": multiline,
            "password": password,
            "on_change": on_change,
            "on_enter": on_enter,
        }
        return TextEditWidget(widget_id, self.widget_name, props)

    def handle_event(self, widget: Widget, event: Event) -> None:
        value = str(event.payload.get("value", ""))
        if event.type == "change":
            widget.update(value=value)
            callback = widget.props.get("on_change")
            if callback is not None:
                callback(value)
        elif event.type == "enter":
            callback = widget.props.get("on_enter")
            if callback is not None:
                callback(value)
