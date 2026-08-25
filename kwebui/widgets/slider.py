"""Slider widget: pick a number from a range, Streamlit ``st.slider`` style."""

from __future__ import annotations

from typing import Callable

from ..events import Event
from ..plugin import WidgetPlugin
from ..widget import Widget


class SliderWidget(Widget):
    @property
    def value(self) -> float:
        return float(self.props.get("value", 0))

    def set_value(self, value: float) -> "SliderWidget":
        self.update(value=value)
        return self


class SliderPlugin(WidgetPlugin):
    """
    Example:
        app.slider("Volume", min_value=0, max_value=100, value=50, on_change=set_volume)
    """

    widget_name = "slider"

    def create(
        self,
        widget_id: str,
        label: str = "",
        *,
        min_value: float = 0.0,
        max_value: float = 100.0,
        value: float | None = None,
        step: float = 1.0,
        on_change: Callable[[float], None] | None = None,
    ) -> SliderWidget:
        props = {
            "label": label,
            "min_value": min_value,
            "max_value": max_value,
            "value": min_value if value is None else value,
            "step": step,
            "on_change": on_change,
        }
        return SliderWidget(widget_id, self.widget_name, props)

    def handle_event(self, widget: Widget, event: Event) -> None:
        if event.type == "change":
            value = float(event.payload.get("value", widget.props.get("value", 0)))
            widget.update(value=value)
            callback = widget.props.get("on_change")
            if callback is not None:
                callback(value)
