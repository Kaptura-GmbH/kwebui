"""Popup widget: a modal dialog with a fixed set of answer buttons.

Renders on the frontend via the native HTML ``<dialog>`` element (see
``popup.js``) rather than a hand-rolled overlay -- Vue has no built-in
modal component of its own, but ``<dialog>``/``showModal()`` is the
platform's equivalent (backdrop, focus trap, Escape-to-cancel all come
for free), and Vue drives its lifecycle exactly like any other widget.

A popup is one-shot: answering it (see ``handle_event``) removes it from
the page tree and tells every connected browser to remove it too, so it
never "replays" for a browser that connects afterwards -- unlike
``ToastWidget``/``AlertWidget``, which stay in the tree forever (see
``toast.py``).
"""

from __future__ import annotations

from typing import Callable

from ..events import Event
from ..plugin import WidgetPlugin
from ..widget import Widget

#: kind -> the buttons it presents, in display order.
_BUTTON_SETS: dict[str, tuple[str, ...]] = {
    "ok": ("ok",),
    "okcancel": ("ok", "cancel"),
    "yesno": ("yes", "no"),
    "yesnocancel": ("yes", "no", "cancel"),
}


class PopupWidget(Widget):
    """
    A popup only matters if it's created *from* a callback (e.g. a button's
    ``on_click``) -- see ``AlertWidget`` in ``alert.py`` for why overriding
    the ``_app`` property is what makes ``self.popup(...)`` broadcast
    immediately instead of silently waiting for the next full page load.
    """

    @property
    def _app(self):
        return self.__dict__.get("_app_ref")

    @_app.setter
    def _app(self, app):
        self.__dict__["_app_ref"] = app
        if app is not None:
            app._on_widget_changed(self)


class PopupPlugin(WidgetPlugin):
    """
    Example:
        self.popup("Delete this item?", kind="yesno", on_return=self.on_delete_answer)

    ``on_return`` is called with one of the strings in the chosen
    ``kind``'s button set ("ok", "cancel", "yes", or "no").
    """

    widget_name = "popup"

    def create(
        self,
        widget_id: str,
        message: str,
        *,
        title: str = "",
        kind: str = "ok",
        on_return: Callable[[str], None] | None = None,
    ) -> PopupWidget:
        if kind not in _BUTTON_SETS:
            available = ", ".join(sorted(_BUTTON_SETS))
            raise ValueError(f"Unknown popup kind {kind!r}. Available: {available}")
        props = {
            "title": title,
            "message": message,
            "buttons": list(_BUTTON_SETS[kind]),
            "on_return": on_return,
        }
        return PopupWidget(widget_id, self.widget_name, props)

    def handle_event(self, widget: Widget, event: Event) -> None:
        if event.type != "answer":
            return
        answer = event.payload.get("answer")
        callback = widget.props.get("on_return")
        if callback is not None:
            callback(answer)
        widget.remove()
