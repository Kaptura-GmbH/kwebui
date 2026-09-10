"""One active browser connection.

Sessions are created and destroyed by the WebSocket layer
(``websocket.py``); normal widget code never constructs one. They exist
so advanced users have somewhere to hang per-connection data
(``app.session.state``) without the framework forcing session handling on
everyone -- see decisions.md for why the widget tree itself is shared
across sessions rather than cloned per session.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from .state import SessionState

if TYPE_CHECKING:
    from fastapi import WebSocket


class Session:
    """A single connected browser tab."""

    def __init__(self, session_id: str, websocket: "WebSocket") -> None:
        self.id = session_id
        self.websocket = websocket
        self.state = SessionState()
        # See request_close()/wait_for_close() below.
        self._close_requested = asyncio.Event()
        self._close_code: int | None = None

    async def send(self, message: dict[str, Any]) -> None:
        await self.websocket.send_json(message)

    def request_close(self, code: int) -> None:
        """Ask this session's own websocket_endpoint task (websocket.py)
        to close the connection with ``code``, the next time it's between
        receives -- used by single_session's supersede and KApp.exit().

        Deliberately does NOT call ``self.websocket.close()`` here: that
        would run on the *caller's* task (a different tab's connection, or
        exit()'s own coroutine), while this session's own task may at the
        very same moment be suspended inside ``await websocket.receive_json()``
        on the very same socket. Starlette's WebSocket assumes a single
        task owns both sending and receiving on a connection -- closing it
        from a second task races the first line of ``close()`` (which sets
        ``application_state = DISCONNECTED`` synchronously, before any
        await) against that task's own state checks, and can surface as a
        raw ``RuntimeError: WebSocket is not connected`` instead of the
        clean ``WebSocketDisconnect`` every caller here expects. Signaling
        the owning task to close itself avoids the cross-task mutation
        entirely."""
        self._close_code = code
        self._close_requested.set()

    async def wait_for_close(self) -> int:
        """Resolves with the requested close code once request_close() is
        called. Meant to be raced (via asyncio.wait) against this
        session's own receive_json() call -- see websocket.py."""
        await self._close_requested.wait()
        assert self._close_code is not None
        return self._close_code

    def __repr__(self) -> str:
        return f"<Session id={self.id!r}>"
