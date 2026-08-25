"""Turns the live widget tree into the JSON structure the frontend renders.

This module never knows what a "button" or "text" widget is -- it only
asks the registry for the right plugin and calls ``serialize`` on it.
"""

from __future__ import annotations

from typing import Any

from .page import Page
from .registry import WidgetRegistry
from .widget import Widget


def serialize_widget(widget: Widget, registry: WidgetRegistry) -> dict[str, Any]:
    plugin = registry.get(widget.widget_type)
    data = plugin.serialize(widget)
    data["children"] = [serialize_widget(child, registry) for child in widget.children]
    return data


def serialize_page(page: Page, registry: WidgetRegistry) -> list[dict[str, Any]]:
    return [serialize_widget(widget, registry) for widget in page.children]
