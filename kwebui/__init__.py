"""kwebui: build web UIs in pure Python, no HTML/CSS/JS required.

    from kwebui import KApp

    class Demo(KApp):
        def build(self) -> None:
            self.text("Hello World", size=28)
            self.button("Click Me", on_click=lambda: print("Clicked"))

    Demo(title="Demo").run()

See docs/architecture.md for how the plugin system, rendering pipeline,
and session lifecycle fit together.
"""

from importlib.metadata import PackageNotFoundError, version

from .app import KApp
from .events import Event
from .plugin import WidgetPlugin
from .widget import Widget

try:
    # Single source of truth: pyproject.toml's [project].version, read from
    # the installed package's own metadata -- not hand-duplicated here, so
    # bumping the version in one place can't leave this constant stale.
    __version__ = version("kwebui")
except PackageNotFoundError:
    # Running from a raw checkout that was never pip-installed (editable or
    # otherwise) -- there is no installed metadata to read.
    __version__ = "0.0.0+unknown"

__all__ = ["KApp", "Event", "Widget", "WidgetPlugin", "__version__"]
