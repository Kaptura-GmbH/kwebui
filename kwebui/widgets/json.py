"""JSON widget: pretty-printed, read-only JSON data, Streamlit ``st.json`` style."""

from __future__ import annotations

from typing import Any

from ..plugin import WidgetPlugin
from ..widget import Widget


class JsonWidget(Widget):
    def set_data(self, data: Any) -> "JsonWidget":
        self.update(data=data)
        return self


class JsonPlugin(WidgetPlugin):
    """
    Example:
        app.json({"status": "ok", "items": [1, 2, 3]})
    """

    widget_name = "json"

    def create(self, widget_id: str, data: Any) -> JsonWidget:
        return JsonWidget(widget_id, self.widget_name, {"data": data})
