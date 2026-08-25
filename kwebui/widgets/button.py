"""Button widget: a clickable control that runs a Python callback."""

from __future__ import annotations

from typing import Callable

from ..events import Event
from ..plugin import WidgetPlugin
from ..widget import Widget


class ButtonWidget(Widget):
    def set_enabled(self, enabled: bool) -> "ButtonWidget":
        self.update(enabled=enabled)
        return self

    def set_text(self, text: str) -> "ButtonWidget":
        self.update(text=text)
        return self

    def set_shortkey(self, shortkey: str | None) -> "ButtonWidget":
        """Change (or clear, with ``None``) the keyboard shortcut that
        triggers this button's ``on_click`` -- see ``create()``'s
        docstring for the accepted format and when it fires."""
        self.update(shortkey=shortkey)
        return self

    def set_color(self, color: str | None) -> "ButtonWidget":
        """Change (or clear, with ``None``) the button's background color.
        See ``create()``'s docstring for accepted values."""
        self.update(color=color)
        return self

    def set_text_color(self, text_color: str | None) -> "ButtonWidget":
        """Change (or clear, with ``None``) the button's text color."""
        self.update(text_color=text_color)
        return self


class ButtonPlugin(WidgetPlugin):
    """
    Example:
        app.button("Save", on_click=save_handler)
        app.button("Search", on_click=search, shortkey="ctrl+k")
        app.button("Delete", on_click=delete, color="red", text_color="white")
    """

    widget_name = "button"

    def create(
        self,
        widget_id: str,
        text: str,
        *,
        on_click: Callable[[], None] | None = None,
        enabled: bool = True,
        shortkey: str | None = None,
        color: str | None = None,
        text_color: str | None = None,
    ) -> ButtonWidget:
        """``shortkey`` binds a keyboard combo (e.g. ``"k"``, ``"shift+k"``,
        ``"ctrl+k"``, ``"shift+ctrl+k"`` -- modifiers in any order, joined
        with ``+``) that calls ``on_click`` exactly as if the button had
        been clicked. The browser listens globally, but only fires it while
        this specific button is actually visible on the page (not
        `.hide()`-den, and not inside a hidden container/sidebar/etc.) and
        `enabled` -- a hidden or disabled button's shortkey is inert, same
        as its click would be. Bare/shift-only combos are additionally
        suppressed while focus is in a text input/textarea/contenteditable
        element, so typing isn't hijacked; a combo that includes
        ctrl/alt/meta still fires even while typing (the common convention
        for e.g. a "Ctrl+K" command shortcut).

        ``color`` sets the button's background; ``text_color`` sets its
        text. Both default to ``None``, which means "use the theme's own
        default" (``--sg-button-bg``/``--sg-button-text-color`` in
        ``base.css``, themselves defaulting to `--sg-accent`/
        `--sg-accent-fg` -- exactly today's rendering, unchanged) rather
        than a hardcoded color here -- restyle those two variables to
        change every button's default color at once, or pass an explicit
        value to override just this one instance. Any valid CSS color
        works: a name ("red", "black", "purple", ...), a hex code
        ("#16a34a"), `rgb(...)`, etc. -- passed straight through to the
        browser with no validation on this end, same as `text`'s own
        `color` param. An invalid value is simply ignored by the browser
        (falls back to the theme color) rather than erroring, so a typo
        degrades gracefully instead of crashing anything.
        """
        props = {
            "text": text,
            "enabled": enabled,
            "on_click": on_click,
            "shortkey": shortkey,
            "color": color,
            "text_color": text_color,
        }
        return ButtonWidget(widget_id, self.widget_name, props)

    def handle_event(self, widget: Widget, event: Event) -> None:
        # "shortkey" (fired by the frontend's global keydown listener once
        # it's matched, visible, and enabled -- see shortkeys.js) is
        # treated identically to a real "click": same callback, same
        # enabled guard, so a keyboard-triggered press can never bypass
        # what a mouse click itself already respects.
        if event.type in ("click", "shortkey") and widget.props.get("enabled", True):
            callback = widget.props.get("on_click")
            if callback is not None:
                callback()
