"""Automatic discovery and lookup of widget plugins.

This is the only place that knows the ``widgets/`` package exists. It
walks every module in that package, picks up any class that subclasses
``WidgetPlugin`` and is defined directly in that module (not merely
imported by it), and indexes an instance of it by name. Adding a new
widget is therefore just "drop a file in ``widgets/``" -- nothing here
needs to change.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil

from . import widgets as widgets_package
from .plugin import WidgetPlugin


class WidgetRegistry:
    """Looks up a ``WidgetPlugin`` by its widget name or alias."""

    def __init__(self) -> None:
        self._plugins_by_name: dict[str, WidgetPlugin] = {}

    def discover(self) -> "WidgetRegistry":
        """Import every module under ``widgets/`` and register its plugins."""
        for module_info in pkgutil.iter_modules(widgets_package.__path__, prefix=f"{widgets_package.__name__}."):
            module = importlib.import_module(module_info.name)
            for _, obj in inspect.getmembers(module, inspect.isclass):
                is_own_plugin = issubclass(obj, WidgetPlugin) and obj is not WidgetPlugin and obj.__module__ == module.__name__
                if is_own_plugin:
                    self.register(obj())
        return self

    def register(self, plugin: WidgetPlugin) -> None:
        for name in (plugin.widget_name, *plugin.aliases):
            self._plugins_by_name[name] = plugin

    def get(self, widget_name: str) -> WidgetPlugin:
        try:
            return self._plugins_by_name[widget_name]
        except KeyError:
            available = ", ".join(sorted(self.names()))
            raise ValueError(f"No widget plugin registered for {widget_name!r}. Available: {available}") from None

    def names(self) -> list[str]:
        """All names (including aliases) that resolve to a plugin."""
        return list(self._plugins_by_name)

    def unique_plugins(self) -> list[WidgetPlugin]:
        """Every registered plugin instance, de-duplicated (aliases share one instance)."""
        seen: dict[int, WidgetPlugin] = {}
        for plugin in self._plugins_by_name.values():
            seen[id(plugin)] = plugin
        return list(seen.values())
