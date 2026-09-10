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
    4002 (SHUTDOWN_CLOSE_CODE) -- KApp.exit() (or Ctrl+C/SIGTERM, which
        uvicorn already turns into the same graceful stop) is stopping
        the app on purpose. Also must NOT reconnect: the process isn't
        coming back, so retrying would just be a silent, endless loop of
        connection-refused errors -- see websocket.js.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .renderer import serialize_page
from .session import Session

if TYPE_CHECKING:
    from .app import KApp

router = APIRouter()

#: Application-private close codes (the 4000-4999 range is reserved for
#: exactly this). See this module's docstring.
SUPERSEDED_CLOSE_CODE = 4001
SHUTDOWN_CLOSE_CODE = 4002


def _close_all_sessions(app: "KApp", code: int) -> None:
    """Disconnect every currently-connected tab with the given close code
    -- SUPERSEDED_CLOSE_CODE for KApp(single_session=True) superseding
    older tabs, or SHUTDOWN_CLOSE_CODE for KApp.exit().

    Each one is dropped from ``app._sessions`` immediately (synchronously
    -- there is nothing to await here, see Session.request_close), so a
    broadcast racing in from another task can't try to write to a socket
    that's on its way out. The actual ``websocket.close()`` call happens
    later, on each session's *own* task -- see websocket_endpoint's loop.
    """
    for session in list(app._sessions):
        app._remove_session(session)
        session.request_close(code)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    app: "KApp" = websocket.app.state.kwebui_app
    await websocket.accept()

    session = Session(session_id=uuid.uuid4().hex, websocket=websocket)
    if app.single_session:
        _close_all_sessions(app, SUPERSEDED_CLOSE_CODE)
    app._add_session(session)
    await session.send({
        "op": "init",
        "theme": app.theme,
        "run_id": app.run_id,
        "widgets": serialize_page(app.page, app.registry),
    })

    try:
        while True:
            # Raced against wait_for_close() rather than plain
            # `await websocket.receive_json()` -- this session can be
            # asked to close at any time (single_session's supersede, or
            # KApp.exit()) by a *different* task (another tab's own
            # connection, or exit()'s coroutine). Starlette's WebSocket
            # assumes one task owns both send and receive on a
            # connection, so that other task must never call
            # websocket.close() itself -- see Session.request_close()'s
            # docstring for what goes wrong if it does. Racing these two
            # lets this task keep sole ownership: it calls close() itself,
            # from right here, once asked.
            receive_task = asyncio.ensure_future(websocket.receive_json())
            close_task = asyncio.ensure_future(session.wait_for_close())
            done, pending = await asyncio.wait(
                {receive_task, close_task}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

            if close_task in done:
                await websocket.close(code=close_task.result())
                break

            message = receive_task.result()
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
