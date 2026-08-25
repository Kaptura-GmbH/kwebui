"""The public entry point: ``from kwebui import KApp``.

``KApp`` deliberately contains no widget-specific code. Calls like
``app.text(...)`` or ``app.button(...)`` do not exist as real methods --
they are resolved dynamically through ``__getattr__`` against whatever
plugins the registry discovered. This is what "core knows nothing about
individual widgets" means in practice: delete every file under
``widgets/`` and ``KApp`` still imports and runs, it just has no widget
methods left.
"""

from __future__ import annotations

import asyncio
import contextvars
import itertools
import re
import socket
from pathlib import Path
from typing import Any

from .page import Page
from .registry import WidgetRegistry
from .renderer import serialize_widget
from .session import Session
from .theme import DEFAULT_THEME, available_themes
from .widget import Widget

_current_session: contextvars.ContextVar[Session | None] = contextvars.ContextVar("current_session", default=None)


def _sanitize_theme_name(stem: str) -> str:
    """Turn a CSS file's stem into a safe theme name: it becomes both a
    URL path segment (``/themes/<name>.css``) and a dict key, so anything
    outside ``[a-zA-Z0-9_-]`` (spaces, dots from a second extension, ...)
    is collapsed to ``_`` rather than passed through as-is."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", stem)


def _bind_free_port(host: str, start_port: int) -> socket.socket:
    """Bind and return a listening socket on the first free port at or
    after ``start_port``. The socket is handed straight to uvicorn (see
    ``KApp.run``) instead of just reporting the port number, so there is
    no gap between "found a free port" and "claimed it" for another
    process to race into.
    """
    port = start_port
    while True:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            sock.close()
            port += 1
            continue
        return sock


class KApp:
    """A kwebui application.

    Subclass it and override ``build()`` to construct the page once by
    calling widget methods (``self.text(...)``, ``self.button(...)``,
    ...) -- ``build()`` runs automatically at the end of ``__init__``.
    Each call adds a live ``Widget`` to the page and returns it so you
    can store it on ``self`` and mutate it later from a callback
    (``widget.update(...)`` or a plugin's typed setters).

        class Demo(KApp):
            def build(self) -> None:
                self.text("Hello World", size=28)

        Demo(title="Demo").run()

    ``width`` caps the main content column's width in CSS pixels (the
    ``#app-root`` element) -- e.g. ``Demo(title="Demo", width=900).run()``.
    Left at the default ``None``, the page uses its original fixed 720px
    cap (see ``base.css``'s ``--sg-app-width`` fallback); this is a one-time,
    page-load-time layout setting, not a live widget prop -- there is no
    ``set_width()`` for it, unlike the per-widget ``width``/``stretch``
    convention (`container`, `table`, `image`, ...) where ``-1``/``0`` means
    "size to content". A `sidebar()`/`topbar()` on the page still narrows the
    available space the same way regardless of this cap (see `docs/architecture.md`).
    """

    def __init__(self, title: str = "kwebui app", width: float | None = None) -> None:
        self.title = title
        self.width = width
        self.page = Page()
        self.registry = WidgetRegistry().discover()
        self.theme = DEFAULT_THEME
        self._custom_themes: dict[str, Path] = {}
        self._sessions: list[Session] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._id_counter = itertools.count(1)
        self.build()

    def build(self) -> None:
        """Override in a subclass to construct the page's widgets. No-op by default."""

    # -- dynamic widget factory -------------------------------------------------

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        registry = self.__dict__.get("registry")
        if registry is None or name not in registry.names():
            raise AttributeError(name)

        def factory(*args: Any, **kwargs: Any) -> Widget:
            widget = registry.get(name).create(self._next_id(), *args, **kwargs)
            widget._app = self
            self.page.add(widget)
            # Broadcast on creation too, not just on later .update() calls,
            # so a widget created from inside a callback (after the initial
            # page load) actually reaches already-connected browsers -- the
            # frontend mounts an unrecognized widget id fresh on first sight.
            self._on_widget_changed(widget)
            return widget

        return factory

    def _next_id(self) -> str:
        return f"w{next(self._id_counter)}"

    # -- theming ------------------------------------------------------------

    def set_theme(self, name: str) -> None:
        """Switch the active theme, live -- every already-connected browser
        swaps its stylesheet immediately, no page reload.

        ``name`` is either a bundled theme name (``"light"``/``"dark"`` out
        of the box, see ``available_themes()``) or a path to your own CSS
        file, anywhere on disk -- absolute, or relative to the current
        working directory. Passing a path is what lets an app supply a
        fully custom theme without touching the installed kwebui package
        itself: the file is read from wherever it actually lives, each
        time a browser (or a later-connecting one) requests it, so editing
        it on disk and calling ``set_theme()`` again picks up the change.
        The theme's name becomes the file's own stem, sanitized
        (``my_theme.css`` -> ``"my_theme"``) -- pass that derived name (or
        the same path again) to switch back to it later; a name collision
        with a bundled theme is resolved in the custom file's favor for
        this app. A custom theme file must define the same ``--sg-*``
        custom properties as ``kwebui/themes/light.css``/``dark.css`` (see
        `docs/user-guide.md`'s Themes section) -- kwebui does not validate
        that; a variable a custom theme forgets to define just falls back
        to the browser's own initial/inherited value wherever it's used,
        rather than erroring.
        """
        if name in available_themes() or name in self._custom_themes:
            self.theme = name
            self._broadcast({"op": "theme", "name": name})
            return

        path = Path(name)
        if path.is_file():
            theme_name = _sanitize_theme_name(path.stem)
            self._custom_themes[theme_name] = path
            self.theme = theme_name
            self._broadcast({"op": "theme", "name": theme_name})
            return

        raise ValueError(
            f"Unknown theme {name!r}: not a bundled theme "
            f"({', '.join(available_themes())}) and not an existing CSS file path."
        )

    # -- session access for advanced users -----------------------------------

    @property
    def session(self) -> Session | None:
        """The session handling the event currently being processed, or None."""
        return _current_session.get()

    # -- internals used by websocket.py / router.py / Widget.update ---------

    def _add_session(self, session: Session) -> None:
        self._sessions.append(session)

    def _remove_session(self, session: Session) -> None:
        if session in self._sessions:
            self._sessions.remove(session)

    async def _dispatch_event(self, session: Session, widget_id: str, event_type: str, payload: dict[str, Any]) -> None:
        from .events import Event

        widget = self.page.find(widget_id)
        if widget is None:
            return
        plugin = self.registry.get(widget.widget_type)
        event = Event(widget_id=widget_id, type=event_type, payload=payload)
        token = _current_session.set(session)
        try:
            # Off the event loop: a blocking callback (time.sleep, a
            # camera read, ...) must not freeze broadcasting to every
            # other connected browser while it runs. asyncio.to_thread
            # propagates contextvars, so app.session still resolves
            # correctly inside the callback despite running on another thread.
            await asyncio.to_thread(plugin.handle_event, widget, event)
        finally:
            _current_session.reset(token)

    def _on_widget_changed(self, widget: Widget) -> None:
        message = {"op": "update", "widget": serialize_widget(widget, self.registry)}
        self._broadcast(message)

    def _remove_widget(self, widget: Widget) -> None:
        """Drop a one-shot widget (e.g. an answered popup) from the page
        tree and tell every connected browser to remove it too."""
        self.page.remove(widget.id)
        self._broadcast({"op": "remove", "widget_id": widget.id})

    def _broadcast(self, message: dict[str, Any]) -> None:
        if not self._sessions or self._loop is None:
            return
        for session in list(self._sessions):
            asyncio.run_coroutine_threadsafe(self._safe_send(session, message), self._loop)

    async def _safe_send(self, session: Session, message: dict[str, Any]) -> None:
        try:
            await session.send(message)
        except Exception:
            self._remove_session(session)

    # -- serving --------------------------------------------------------------

    def run(self, host: str = "127.0.0.1", port: int = 8701, *, log_level: str = "info") -> None:
        """Start the web server. Blocks until interrupted.

        If ``port`` is already in use, tries ``port + 1``, ``port + 2``, ...
        until one is free.
        """
        import uvicorn

        from .router import build_fastapi_app

        sock = _bind_free_port(host, port)
        bound_port = sock.getsockname()[1]
        if bound_port != port:
            print(f"Port {port} is in use; using {bound_port} instead.", flush=True)

        fastapi_app = build_fastapi_app(self)
        config = uvicorn.Config(fastapi_app, log_level=log_level)
        # uvicorn skips its own "Uvicorn running on ..." banner whenever
        # sockets= is passed explicitly (it assumes a multi-worker setup
        # already logged that via config.bind_socket()) -- print it
        # ourselves instead, since that's the one line that actually
        # matters for finding the app.
        print(f"kwebui app running on http://{host}:{bound_port} (Press CTRL+C to quit)", flush=True)
        uvicorn.Server(config).run(sockets=[sock])
