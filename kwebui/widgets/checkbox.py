"""Checkbox widget: a labelled boolean toggle."""

from __future__ import annotations

from typing import Callable

from ..events import Event
from ..plugin import WidgetPlugin
from ..widget import Widget


class CheckboxWidget(Widget):
    @property
    def checked(self) -> bool:
        return bool(self.props.get("checked", False))

    def set_checked(self, checked: bool) -> "CheckboxWidget":
        self.update(checked=checked)
        return self


class CheckboxPlugin(WidgetPlugin):
    """
    Example:
        app.checkbox("Enable feature", on_change=lambda checked: print(checked))
    """

    widget_name = "checkbox"

    def create(
        self,
        widget_id: str,
        label: str,
        *,
        checked: bool = False,
        on_change: Callable[[bool], None] | None = None,
    ) -> CheckboxWidget:
        props = {"label": label, "checked": checked, "on_change": on_change}
        return CheckboxWidget(widget_id, self.widget_name, props)

    def handle_event(self, widget: Widget, event: Event) -> None:
        if event.type == "change":
            checked = bool(event.payload.get("checked", False))
            widget.update(checked=checked)  # re-broadcasts so other connected sessions stay in sync
            callback = widget.props.get("on_change")
            if callback is not None:
                callback(checked)
