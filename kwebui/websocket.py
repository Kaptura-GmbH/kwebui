"""The single WebSocket endpoint every client connects to.

Protocol (JSON messages), server -> client:
    {"op": "init",   "theme": str, "run_id": str, "widgets": [...]}
                                                       -- sent once on connect
                                                       -- run_id identifies the
                                                          server *process* (see
                                                          KApp.run_id)
    {"op": "update", "widget": {...}}                  -- one widget (sub)tree changed
    {"op": "theme",  "name": str}                      -- theme switched
    {"op": "focus",  "widget_id": str}                 -- send keyboard focus to a widget
    {"op": "remove", "widget_id": str}                 -- a widget (e.g. an answered popup) is gone

Protocol, client -> server:
    {"widget_id": str, "type": str, "payload": {...}}  -- a UI event

Close codes, server -> client:
    4001 (SUPERSEDED_CLOSE_CODE)  -- only in KApp(single_session=True): a
        newer tab connected, so this one was deliberately disconnected.
        Distinct from an ordinary close specifically so the browser can
        tell "you were replaced" from "the server went away" -- see
        websocket.js, which must NOT reconnect on this code.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .renderer import serialize_page
from .session import Session

if TYPE_CHECKING:
    from .app import KApp

router = APIRouter()

#: Application-private close code (the 4000-4999 range is reserved for
#: exactly this) telling a browser it was replaced by a newer tab rather
#: than losing the server. See this module's docstring.
SUPERSEDED_CLOSE_CODE = 4001


async def _supersede_existing_sessions(app: "KApp") -> None:
    """Disconnect every currently-connected tab, for KApp(single_session=True).

    Each one is dropped from ``app._sessions`` *before* its socket is
    closed, so a broadcast racing in from another task can't try to write
    to a socket that's on its way out.
    """
    for previous in list(app._sessions):
        app._remove_session(previous)
        try:
            await previous.websocket.close(code=SUPERSEDED_CLOSE_CODE)
        except Exception:
            # Already gone (browser closed the tab, network dropped, ...)
            # -- it's being disconnected anyway, so nothing to recover.
            pass


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    app: "KApp" = websocket.app.state.kwebui_app
    await websocket.accept()

    session = Session(session_id=uuid.uuid4().hex, websocket=websocket)
    if app.single_session:
        await _supersede_existing_sessions(app)
    app._add_session(session)
    await session.send({
        "op": "init",
        "theme": app.theme,
        "run_id": app.run_id,
        "widgets": serialize_page(app.page, app.registry),
    })

    try:
        while True:
            message = await websocket.receive_json()
            await app._dispatch_event(
                session,
                widget_id=message["widget_id"],
                event_type=message["type"],
                payload=message.get("payload", {}),
            )
    except WebSocketDisconnect:
        pass
    finally:
        app._remove_session(session)
