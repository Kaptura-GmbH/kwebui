"""Supplying your own theme as a plain CSS file, from your own project --
no need to touch the installed kwebui package. Run with:

    python examples/custom_theme.py

`set_theme()` accepts either a bundled theme name ("light"/"dark") or a
path to any CSS file that defines the same `--sg-*` custom properties
(see `docs/user-guide.md`'s Themes section for the full list). Passing a
path registers it under a name derived from the file's own stem
(`brand.css` -> "brand"); pass that name again later to switch back to
it without repeating the path.
"""
from __future__ import annotations

from pathlib import Path

from kwebui import KApp

THEME_FILE = Path(__file__).parent / "assets" / "brand_theme.css"


class CustomThemeDemo(KApp):
    def build(self) -> None:
        # Calling set_theme() here, during build(), sets the theme that's
        # already active for the very first page load -- no flash of the
        # default theme before it switches.
        self.set_theme(str(THEME_FILE))

        self.text("Custom theme from examples/assets/brand_theme.css", size=22, bold=True)
        self.text("Edit that file and reload the page to see the change.", color="#6b7280")
        self.button("A themed button")

        self.text("Switch themes live -- every connected browser updates immediately:", size=16, bold=True)
        self.button("Bundled dark", on_click=lambda: self.set_theme("dark"))
        self.button("Bundled light", on_click=lambda: self.set_theme("light"))
        # Switching back only needs the derived name, not the path again.
        self.button("Back to brand theme", on_click=lambda: self.set_theme("brand_theme"))


if __name__ == "__main__":
    CustomThemeDemo(title="Custom Theme Demo").run()
