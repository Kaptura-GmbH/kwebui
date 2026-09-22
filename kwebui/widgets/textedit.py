"""TextEdit widget: a single-line or multi-line text input."""

from __future__ import annotations

from typing import Callable

from ..events import Event
from ..plugin import WidgetPlugin
from ..widget import Widget


def _clamp(value: str, max_length: int | None) -> str:
    """Truncate to ``max_length`` if one is set. Used everywhere a value
    can enter the widget -- ``create()``, ``set_value()``, and an
    incoming ``change`` event -- so ``max_length`` holds regardless of
    which of those put the value there.
    """
    if max_length is not None and len(value) > max_length:
        return value[:max_length]
    return value


class TextEditWidget(Widget):
    @property
    def value(self) -> str:
        return str(self.props.get("value", ""))

    def set_value(self, value: str) -> "TextEditWidget":
        self.update(value=_clamp(value, self.props.get("max_length")))
        return self

    def set_max_length(self, max_length: int | None) -> "TextEditWidget":
        """Changing this live can leave the *current* value over the new
        limit (typing more, then setting a smaller cap, shouldn't quietly
        eat what's already there without the app author asking for that
        explicitly) -- it only clamps forward, on the next edit or the
        next explicit ``set_value()``, not retroactively."""
        self.update(max_length=max_length)
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
        max_length: int | None = None,
        on_change: Callable[[str], None] | None = None,
        on_enter: Callable[[str], None] | None = None,
    ) -> TextEditWidget:
        props = {
            "label": label,
            "value": _clamp(value, max_length),
            "placeholder": placeholder,
            "multiline": multiline,
            "password": password,
            "max_length": max_length,
            "on_change": on_change,
            "on_enter": on_enter,
        }
        return TextEditWidget(widget_id, self.widget_name, props)

    def handle_event(self, widget: Widget, event: Event) -> None:
        # The client enforces max_length via the native `maxlength`
        # attribute, but a raw WebSocket message could bypass that, so
        # it's re-clamped here too.
        value = _clamp(str(event.payload.get("value", "")), widget.props.get("max_length"))
        if event.type == "change":
            widget.update(value=value)
            callback = widget.props.get("on_change")
            if callback is not None:
                callback(value)
        elif event.type == "enter":
            callback = widget.props.get("on_enter")
            if callback is not None:
                callback(value)
