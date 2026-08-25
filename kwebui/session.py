"""One active browser connection.

Sessions are created and destroyed by the WebSocket layer
(``websocket.py``); normal widget code never constructs one. They exist
so advanced users have somewhere to hang per-connection data
(``app.session.state``) without the framework forcing session handling on
everyone -- see decisions.md for why the widget tree itself is shared
across sessions rather than cloned per session.
"""

from __future__ import annotations

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

    async def send(self, message: dict[str, Any]) -> None:
        await self.websocket.send_json(message)

    def __repr__(self) -> str:
        return f"<Session id={self.id!r}>"
