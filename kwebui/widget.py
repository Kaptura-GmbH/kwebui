"""The core, widget-agnostic building block of every UI tree.

This module is intentionally the only place the core framework knows what
a "widget" looks like structurally. It has no idea that "button" or "text"
exist -- that knowledge lives entirely in the plugins under ``widgets/``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .app import KApp


class Widget:
    """A live node in the UI tree.

    A ``Widget`` is a small bag of state: an id, a type name (matching a
    registered plugin's ``widget_name``), a dict of JSON-able properties,
    and optional children (used by container-like widgets such as
    ``Empty``). Widget subclasses defined by plugins add typed convenience
    methods (e.g. ``TextWidget.set_text``) but must not add new structural
    fields -- structure stays generic so the core never needs to change.
    """

    def __init__(self, widget_id: str, widget_type: str, props: dict[str, Any] | None = None) -> None:
        self.id = widget_id
        self.widget_type = widget_type
        self.props: dict[str, Any] = props or {}
        self.children: list[Widget] = []
        self.slot_of: str | None = None
        self.highlighted: bool = False
        self.highlight_color: str | None = None
        self.visible: bool = True
        self.enabled: bool = True
        self._app: "KApp | None" = None

    def update(self, **props: Any) -> "Widget":
        """Merge new property values in and push an update patch to clients."""
        self.props.update(props)
        if self._app is not None:
            self._app._on_widget_changed(self)
        return self

    def highlight(self, color: str | None = None) -> "Widget":
        """Draw an attention-grabbing border around this widget.

        Generic across every widget type, since it lives here on the core
        ``Widget`` rather than on any plugin. ``color`` (any valid CSS
        color) overrides the theme's ``--sg-highlight`` variable for this
        widget only; omit it to use that theme default (red unless a
        theme's CSS redefines it).
        """
        self.highlighted = True
        self.highlight_color = color
        if self._app is not None:
            self._app._on_widget_changed(self)
        return self

    def unhighlight(self) -> "Widget":
        """Remove a highlight previously set by ``highlight()``."""
        self.highlighted = False
        self.highlight_color = None
        if self._app is not None:
            self._app._on_widget_changed(self)
        return self

    def hide(self) -> "Widget":
        """Hide this widget without removing it.

        Persistent state like ``highlighted`` -- folded into ``serialize()``'s
        output so a browser connecting later also sees it hidden, rather than
        a one-shot op like ``focus()``/``remove()``. Reversible via ``show()``;
        use ``remove()`` instead when the widget should be gone for good.
        """
        self.visible = False
        if self._app is not None:
            self._app._on_widget_changed(self)
        return self

    def show(self) -> "Widget":
        """Reveal a widget previously hidden by ``hide()``."""
        self.visible = True
        if self._app is not None:
            self._app._on_widget_changed(self)
        return self

    def disable(self) -> "Widget":
        """Make this widget inert, generically across every widget type
        (button, checkbox, textedit, slider, listbox, file_uploader,
        container's shortkey, ...) -- not just the handful that happen to
        have their own notion of "enabled".

        Enforcement lives in one place, ``KApp._dispatch_event``: a
        browser-originated event addressed to a disabled widget is
        dropped before it ever reaches that widget type's own
        ``handle_event()``, so no plugin needs its own "am I enabled"
        check (previously ``button`` re-implemented this itself; every
        other widget type had no way to be disabled at all). The
        frontend mirrors this visually for every widget generically
        (dimmed, not clickable -- see ``renderer.js``'s ``nodeStyle``)
        and, for the widgets with a real native form control, also sets
        that element's own ``disabled`` attribute (see each widget's
        ``.js`` file) so a disabled `textedit`/`listbox`/`slider` can't
        be typed into or operated via keyboard either, not just clicked.

        Reversible via ``enable()``; unlike ``remove()``, the widget and
        its state stay exactly as they were, and unlike ``hide()`` it
        stays visible, just inert."""
        self.enabled = False
        if self._app is not None:
            self._app._on_widget_changed(self)
        return self

    def enable(self) -> "Widget":
        """Allow a widget disabled by ``disable()`` to respond to
        interaction again."""
        self.enabled = True
        if self._app is not None:
            self._app._on_widget_changed(self)
        return self

    def remove(self) -> None:
        """Remove this widget from the page and every connected browser,
        dropping it from server-side memory too.

        Unlike ``hide()``, this is permanent -- there is no corresponding
        "un-remove". See ``KApp._remove_widget`` for the broadcast mechanics.
        """
        if self._app is not None:
            self._app._remove_widget(self)

    def focus(self) -> "Widget":
        """Send keyboard focus to this widget's input element.

        A one-shot command, not persistent state like ``highlighted`` --
        it is broadcast as its own ``{"op": "focus"}`` message (see
        ``KApp._broadcast``) rather than folded into the widget's
        serialized props, so a browser that connects later never
        "replays" a focus that already happened.
        """
        if self._app is not None:
            self._app._broadcast({"op": "focus", "widget_id": self.id})
        return self

    def __repr__(self) -> str:
        return f"<{type(self).__name__} id={self.id!r} type={self.widget_type!r}>"
