"""Spinner widget: a loading indicator, usable as a context manager.

    with app.spinner("Loading data..."):
        do_slow_thing()

kwebui has no rerun model, so unlike Streamlit's ``st.spinner`` the widget
never leaves the tree -- ``__exit__`` just flips ``active`` to ``False``,
which patches every connected browser; the CSS hides it in place
(``display: none``) rather than the DOM node ever being removed.

With ``show_time=True``, a background task ticks the elapsed seconds to
connected browsers roughly every 100ms while the block runs. This only
works because callbacks are dispatched off the event loop (see
``App._dispatch_event``) -- otherwise a blocking call inside the block
(e.g. ``time.sleep(5)``) would also freeze the ticker along with every
other connected browser.
"""

from __future__ import annotations

import asyncio
import time

from ..plugin import WidgetPlugin
from ..widget import Widget


class SpinnerWidget(Widget):
    def __init__(self, widget_id: str, widget_type: str, props: dict) -> None:
        super().__init__(widget_id, widget_type, props)
        self._started: float = 0.0
        self._tick_task: "asyncio.Future | None" = None

    def __enter__(self) -> "SpinnerWidget":
        self._started = time.monotonic()
        self.update(active=True, elapsed=0.0 if self.props.get("show_time") else None)
        loop = self._app._loop if self._app else None
        if loop is not None and self.props.get("show_time"):
            self._tick_task = asyncio.run_coroutine_threadsafe(self._tick(), loop)
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self._tick_task is not None:
            self._tick_task.cancel()
            self._tick_task = None
        elapsed = round(time.monotonic() - self._started, 1) if self.props.get("show_time") else None
        self.update(active=False, elapsed=elapsed)

    async def _tick(self) -> None:
        while True:
            await asyncio.sleep(0.1)
            self.update(elapsed=round(time.monotonic() - self._started, 1))


class SpinnerPlugin(WidgetPlugin):
    """
    Example:
        with app.spinner("Loading data..."):
            do_slow_thing()

        with app.spinner("Working...", show_time=True):
            app.text("This text is shown while the spinner is active.")
            time.sleep(5)
    """

    widget_name = "spinner"

    def create(self, widget_id: str, text: str = "Loading...", *, show_time: bool = False) -> SpinnerWidget:
        return SpinnerWidget(widget_id, self.widget_name, {"text": text, "show_time": show_time, "active": False, "elapsed": None})
