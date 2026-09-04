"""Badge widget: a small pill-shaped status/tag label, Streamlit
``st.badge`` style.

Purely static/display -- no events, no server routes. The only design
decision worth recording: ``color`` is restricted to the same four
semantic levels ``success``/``info``/``warning``/``error`` already used
by the ``alert`` widgets (reusing their exact hex colors -- see
``base.css``), rather than accepting an arbitrary CSS color string. This
keeps a badge visually consistent with every other status indicator in
the app (alert banners, toasts, the workflow tracker) instead of adding
a second, independent color vocabulary.
"""

from __future__ import annotations

from ..plugin import WidgetPlugin
from ..widget import Widget

_LEVELS = ("success", "info", "warning", "error")


class BadgeWidget(Widget):
    def set_text(self, text: str) -> "BadgeWidget":
        self.update(text=text)
        return self

    def set_color(self, color: str | None) -> "BadgeWidget":
        """Change (or clear, with ``None``) the badge's semantic color.
        See ``create()``'s docstring for the accepted values."""
        _validate_color(color)
        self.update(color=color)
        return self

    def set_icon(self, icon: str | None) -> "BadgeWidget":
        """Change (or clear, with ``None``) the badge's leading icon."""
        self.update(icon=icon)
        return self


def _validate_color(color: str | None) -> None:
    if color is not None and color not in _LEVELS:
        raise ValueError(f"badge color must be one of {_LEVELS} or None, got {color!r}.")


class BadgePlugin(WidgetPlugin):
    """
    Example:
        app.badge("New")
        app.badge("Beta", color="info")
        app.badge("Active", icon="✅", color="success")
    """

    widget_name = "badge"

    def create(self, widget_id: str, text: str, *, color: str | None = None, icon: str | None = None) -> BadgeWidget:
        """``color`` is one of ``"success"``/``"info"``/``"warning"``/
        ``"error"`` (the same levels as ``app.success()``/``app.info()``/
        ``app.warning()``/``app.error()``), or ``None`` for a neutral,
        theme-colored badge. Any other value raises ``ValueError``
        immediately rather than silently rendering an unstyled badge.
        ``icon`` is an optional leading emoji/character, shown as-is with
        no default (unlike ``alert``, a badge has no inherent "kind" to
        pick a default icon from)."""
        _validate_color(color)
        props = {"text": text, "color": color, "icon": icon}
        return BadgeWidget(widget_id, self.widget_name, props)
