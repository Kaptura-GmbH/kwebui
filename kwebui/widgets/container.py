"""Container widget: a generic region whose entire content can be
cleared and rebuilt -- used to swap between different "pages" of widgets
while the app keeps running (see ``examples/workflow.py``).

    page = app.container()
    page.text("Page 1")
    ...
    page.clear()          # wipe it
    page.text("Page 2")   # rebuild with different content

Structurally the same append-only container idea as
``ColumnWidget``/``SidebarWidget``/``TopbarWidget`` (same ``__getattr__``
dynamic factory, duplicated rather than shared -- matches the existing
precedent across those modules), plus a ``clear()`` method mirroring
``EmptyWidget.clear()``. The difference from ``Empty`` is exactly that:
``Empty`` holds a single child and replacing it means calling another
``slot.<widget>(...)``, whereas a ``Container`` is meant to hold a whole
group of widgets at once, so swapping its content is "clear(), then
rebuild with several calls" rather than a single replacing call.
"""

from __future__ import annotations

from typing import Any, Callable

from ..events import Event
from ..plugin import WidgetPlugin
from ..widget import Widget


class ContainerWidget(Widget):
    def set_width(self, width: float) -> "ContainerWidget":
        """Resize the container. -1 or 0 falls back to sizing to its
        content. Ignored while ``stretch`` is True."""
        self.update(width=width)
        return self

    def set_height(self, height: float) -> "ContainerWidget":
        """Give the container a fixed height. -1 or 0 falls back to sizing
        to its content, like ``width``'s default -- there is no ``stretch``
        equivalent for height. A fixed height is what makes
        ``vertical_alignment`` visible (see ``create()``'s docstring):
        without one, the container never has more height than its content
        needs, so there's nothing to center within."""
        self.update(height=height)
        return self

    def set_stretch(self, stretch: bool) -> "ContainerWidget":
        """Toggle whether the container fills its parent's width."""
        self.update(stretch=stretch)
        return self

    def set_border(self, border: bool) -> "ContainerWidget":
        """Toggle the container's border."""
        self.update(border=border)
        return self

    def set_border_roundness(self, border_roundness: bool) -> "ContainerWidget":
        """Toggle whether the container's border corners are rounded."""
        self.update(border_roundness=border_roundness)
        return self

    def set_caption(self, caption: str) -> "ContainerWidget":
        """Change the caption shown breaking the top border line.
        Pass "" to remove it."""
        self.update(caption=caption)
        return self

    def set_horizontal_alignment(self, horizontal_alignment: str | None) -> "ContainerWidget":
        """Change how children are aligned along the container's width.
        One of "left"/"center"/"right", or None to go back to filling the
        full width (the default -- see ``create()``'s docstring)."""
        self.update(horizontal_alignment=horizontal_alignment)
        return self

    def set_vertical_alignment(self, vertical_alignment: str | None) -> "ContainerWidget":
        """Change how children are packed along the container's height.
        One of "top"/"center"/"bottom", or None for the default (top --
        only visible once the container has more height than its content
        needs, e.g. given an explicit height by its own parent)."""
        self.update(vertical_alignment=vertical_alignment)
        return self

    def set_shortkey(self, shortkey: str | None) -> "ContainerWidget":
        """Change (or clear, with ``None``) the keyboard shortcut that
        calls ``on_keypress`` -- see ``create()``'s docstring."""
        self.update(shortkey=shortkey)
        return self

    def set_on_keypress(self, on_keypress: Callable[[], None] | None) -> "ContainerWidget":
        """Change (or clear, with ``None``) the callback ``shortkey`` calls."""
        self.update(on_keypress=on_keypress)
        return self

    def set_vertical_padding(self, vertical_padding: float | None) -> "ContainerWidget":
        """Change the space (in px) between the container's top/bottom
        edge and its content, or go back to the theme's own default
        (``--sg-container-padding-vertical`` in ``base.css``) with
        ``None``."""
        self.update(vertical_padding=vertical_padding)
        return self

    def set_horizontal_padding(self, horizontal_padding: float | None) -> "ContainerWidget":
        """Change the space (in px) between the container's left/right
        edge and its content, or go back to the theme's own default
        (``--sg-container-padding-horizontal`` in ``base.css``) with
        ``None``."""
        self.update(horizontal_padding=horizontal_padding)
        return self

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        app = self.__dict__.get("_app")
        if app is None or name not in app.registry.names():
            raise AttributeError(name)

        def factory(*args: Any, **kwargs: Any) -> Widget:
            child = app.registry.get(name).create(app._next_id(), *args, **kwargs)
            # Parent+broadcast before wiring up `_app` -- see EmptyWidget's
            # factory for why the order matters (self-broadcasting widgets
            # like alert/toast/popup/columns would otherwise announce
            # themselves unparented first and get mounted twice).
            self.children.append(child)
            if self._app is not None:
                self._app._on_widget_changed(self)
            child._app = app
            return child

        return factory

    def clear(self) -> "ContainerWidget":
        """Remove all current children -- call before rebuilding with
        different content (e.g. switching to a different "page")."""
        self.children = []
        if self._app is not None:
            self._app._on_widget_changed(self)
        return self


class ContainerPlugin(WidgetPlugin):
    """
    Example:
        page = app.container()
        page.text("Hello")

        card = app.container(width=300, border=True, border_roundness=True)
        wide = app.container(stretch=True, border=False)
        titled = app.container(caption="Settings")  # caption breaks the top border line
        centered = app.container(width=400, horizontal_alignment="center")
        panel = app.container(height=300, vertical_alignment="center")  # a fixed-height "panel"
        panel.button("Centered")  # ... vertically centered inside it
        app.container(shortkey="ctrl+k", on_keypress=open_search)  # fires while this container is visible
        padded = app.container(vertical_padding=16, horizontal_padding=24)  # breathing room around content
    """

    widget_name = "container"

    def create(
        self,
        widget_id: str,
        *,
        width: float = -1,
        height: float = -1,
        stretch: bool = False,
        border: bool = True,
        border_roundness: bool = True,
        caption: str = "",
        horizontal_alignment: str | None = None,
        vertical_alignment: str | None = None,
        shortkey: str | None = None,
        on_keypress: Callable[[], None] | None = None,
        vertical_padding: float | None = None,
        horizontal_padding: float | None = None,
    ) -> ContainerWidget:
        """``horizontal_alignment`` ("left"/"center"/"right") and
        ``vertical_alignment`` ("top"/"center"/"bottom") position children
        within the container's own box, once that box is bigger than its
        content -- e.g. a fixed ``width`` wider than the children, or a
        fixed ``height`` taller than the children.

        Left at the default ``None``, children keep today's original
        behavior: stretched to the container's full width and packed at
        the top, exactly as if this parameter didn't exist. This is a
        deliberate choice, not an oversight -- several widgets with a
        visible border/background (``success()``/``info()``/``warning()``/
        ``error()``, ``listbox``, ``textedit``, ``slider``) rely on that
        implicit full-width stretch from their parent to reach their own
        max-width, not on any width of their own. Picking an explicit
        ``horizontal_alignment`` shrinks every child to its own natural
        size first, *then* aligns it -- so a `listbox`/`textedit`/`slider`
        inside a horizontally-aligned container renders narrower than in
        an unaligned one.

        ``height`` (like ``width``) defaults to ``-1``, sizing to content;
        there is no ``stretch``-for-height equivalent. Unlike
        ``horizontal_alignment``, ``vertical_alignment`` has no
        default-preserving caveat to worry about: a container's height is
        intrinsic (sized to its content) regardless of what
        `vertical_alignment` is set to, so it stays invisible until you
        also give the container a fixed ``height`` (or it's otherwise
        handed extra height by its own parent) -- at which point it
        actually has more room than its content needs, and something to
        center/bottom-align within.

        ``shortkey`` (e.g. ``"k"``, ``"shift+k"``, ``"ctrl+k"``,
        ``"shift+ctrl+k"`` -- modifiers in any order, joined with ``+``)
        binds a keyboard combo that calls ``on_keypress``, following the
        exact same rules as `button`'s `shortkey` (see its docstring):
        global listener, but only fires while this container is actually
        visible on the page (not `.hide()`-den, not inside a hidden
        ancestor), and bare/shift-only combos are suppressed while typing
        in a text field. Unlike `button`, a container has no `on_click` to
        reuse, so it gets its own dedicated `on_keypress` callback instead.

        ``vertical_padding``/``horizontal_padding`` (in px) add space
        between the container's own edge and its content -- top/bottom
        and left/right respectively. Both default to ``None``, which
        means "use the theme's own default" (``--sg-container-padding-
        vertical``/``--sg-container-padding-horizontal`` in ``base.css``,
        `10px` each out of the box) rather than a hardcoded number here --
        restyle the theme variables to change every container's default
        padding at once, or pass an explicit value to override just this
        one instance (pass `0` for none at all, distinct from `None`
        which defers to the theme). Padding is applied inside the border,
        so it doesn't move the border/caption themselves, only the room
        between the border and what's inside.
        """
        props = {
            "width": width,
            "height": height,
            "stretch": stretch,
            "border": border,
            "border_roundness": border_roundness,
            "caption": caption,
            "horizontal_alignment": horizontal_alignment,
            "vertical_alignment": vertical_alignment,
            "shortkey": shortkey,
            "on_keypress": on_keypress,
            "vertical_padding": vertical_padding,
            "horizontal_padding": horizontal_padding,
        }
        return ContainerWidget(widget_id, self.widget_name, props)

    def handle_event(self, widget: Widget, event: Event) -> None:
        # Mirrors ButtonPlugin's "shortkey" handling, but with no "click"
        # equivalent to reuse -- a container's shortkey has always meant
        # on_keypress, there's no separate "real" interaction it aliases.
        if event.type == "shortkey":
            callback = widget.props.get("on_keypress")
            if callback is not None:
                callback()
