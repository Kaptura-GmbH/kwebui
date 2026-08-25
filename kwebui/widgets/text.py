"""Text widget: a styled block of text."""

from __future__ import annotations

from ..plugin import WidgetPlugin
from ..widget import Widget


class TextWidget(Widget):
    def set_text(self, value: str) -> "TextWidget":
        self.update(text=value)
        return self

    def set_color(self, color: str) -> "TextWidget":
        self.update(color=color)
        return self


class TextPlugin(WidgetPlugin):
    """
    Example:
        app.text("Hello", size=24, color="red", bold=True)
    """

    widget_name = "text"

    def create(
        self,
        widget_id: str,
        text: str,
        *,
        size: int = 16,
        color: str = "inherit",
        bold: bool = False,
        italic: bool = False,
        align: str = "left",
    ) -> TextWidget:
        props = {"text": text, "size": size, "color": color, "bold": bold, "italic": italic, "align": align}
        return TextWidget(widget_id, self.widget_name, props)
