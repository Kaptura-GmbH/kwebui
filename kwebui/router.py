"""Builds the FastAPI application: static files, the index page, theme CSS,
the WebSocket endpoint, and any extra routes plugins register for
themselves (see ``WidgetPlugin.register_routes``).
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import theme, websocket

if TYPE_CHECKING:
    from .app import KApp

FRONTEND_DIR = Path(__file__).parent / "frontend"


def build_fastapi_app(app: "KApp") -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        app._loop = asyncio.get_running_loop()
        yield

    fastapi_app = FastAPI(title=app.title, lifespan=lifespan)
    fastapi_app.state.kwebui_app = app

    fastapi_app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")
    templates = Jinja2Templates(directory=FRONTEND_DIR / "templates")

    widget_scripts = sorted(p.name for p in (FRONTEND_DIR / "static" / "js" / "widgets").glob("*.js"))

    # api_route(..., methods=["GET", "HEAD"]) rather than plain get(...):
    # FastAPI's own routing (unlike plain Starlette Route) does not add HEAD
    # support to a GET route automatically, so a HEAD request -- routine for
    # monitoring tools, uptime checks, and some browsers/proxies probing a
    # server before a real GET -- would otherwise 405. FileResponse (used
    # below by theme_css) already omits the body for HEAD on its own; a
    # plain HTMLResponse/TemplateResponse doesn't, so index() checks the
    # method itself rather than rendering and sending the full page for a
    # request that must not have a body.
    @fastapi_app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        if request.method == "HEAD":
            return HTMLResponse(status_code=200)
        return templates.TemplateResponse(
            request,
            "index.html",
            {"title": app.title, "theme": app.theme, "width": app.width, "widget_scripts": widget_scripts},
        )

    @fastapi_app.api_route("/themes/{name}.css", methods=["GET", "HEAD"])
    async def theme_css(name: str) -> FileResponse:
        # A custom theme (registered by set_theme() being given a file
        # path -- see app.py) is checked first, so it wins over a bundled
        # theme of the same name for this app; re-reads from wherever it
        # actually lives on disk on every request, not a one-time copy, so
        # editing the file and calling set_theme() again picks up changes.
        custom_path = app._custom_themes.get(name)
        if custom_path is not None:
            return FileResponse(custom_path, media_type="text/css")
        try:
            path = theme.theme_path(name)
        except ValueError:
            raise HTTPException(status_code=404, detail="Unknown theme")
        return FileResponse(path, media_type="text/css")

    fastapi_app.include_router(websocket.router)

    for plugin in app.registry.unique_plugins():
        plugin.register_routes(fastapi_app, app)

    return fastapi_app
