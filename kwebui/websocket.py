"""The single WebSocket endpoint every client connects to.

Protocol (JSON messages), server -> client:
    {"op": "init",   "theme": str, "widgets": [...]}   -- sent once on connect
    {"op": "update", "widget": {...}}                  -- one widget (sub)tree changed
    {"op": "theme",  "name": str}                      -- theme switched
    {"op": "focus",  "widget_id": str}                 -- send keyboard focus to a widget
    {"op": "remove", "widget_id": str}                 -- a widget (e.g. an answered popup) is gone

Protocol, client -> server:
    {"widget_id": str, "type": str, "payload": {...}}  -- a UI event
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


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    app: "KApp" = websocket.app.state.kwebui_app
    await websocket.accept()

    session = Session(session_id=uuid.uuid4().hex, websocket=websocket)
    app._add_session(session)
    await session.send({
        "op": "init",
        "theme": app.theme,
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
