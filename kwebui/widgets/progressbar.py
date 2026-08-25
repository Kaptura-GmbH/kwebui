"""ProgressBar widget: a determinate percentage or an indeterminate spinner."""

from __future__ import annotations

from ..plugin import WidgetPlugin
from ..widget import Widget


class ProgressBarWidget(Widget):
    def set_value(self, percentage: float) -> "ProgressBarWidget":
        self.update(value=max(0.0, min(100.0, percentage)), indeterminate=False)
        return self

    def set_indeterminate(self, indeterminate: bool = True) -> "ProgressBarWidget":
        self.update(indeterminate=indeterminate)
        return self


class ProgressBarPlugin(WidgetPlugin):
    """
    Example:
        app.progressbar(50)
        app.progressbar(0, indeterminate=True)

    Aliased as "progress" so it also reads naturally inside an Empty slot:
        slot.progress(80)
    """

    widget_name = "progressbar"
    aliases = ("progress",)

    def create(self, widget_id: str, value: float = 0, *, indeterminate: bool = False) -> ProgressBarWidget:
        props = {"value": max(0.0, min(100.0, value)), "indeterminate": indeterminate}
        return ProgressBarWidget(widget_id, self.widget_name, props)
