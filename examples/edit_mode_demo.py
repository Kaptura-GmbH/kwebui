"""Design a page visually, then use it from Python. Run with:

    python examples/edit_mode_demo.py --design     # lay the page out
    python examples/edit_mode_demo.py              # run it for real

The only difference between the two is `edit_mode=True` on the KApp --
this file reads `--design` off sys.argv purely so one example can show
both halves; your own app can just flip the kwarg.

In edit mode:
    1. Every container gets a dashed outline, so you can see the boxes.
    2. Right-click inside one -- a menu opens with a search box. Type to
       filter (e.g. "but"), press Enter or click to insert. The widget
       appears in that container immediately.
    3. Click any widget to select it: its properties show on the right,
       including its **id**, which is the name your Python code uses.
       Rename it to something meaningful like `save_button`.
    4. Fill in a handler name (e.g. `on_save`) for on_click, and implement
       a method of that name on your app -- it is wired up automatically
       on load.
    5. Every change is written straight to edit_mode_demo.layout.json.

Then run it without --design: `load_layout()` rebuilds exactly that page
and hands back a dict keyed by those ids, so `ui["save_button"]` is the
live widget.
"""

from __future__ import annotations

import sys
from pathlib import Path

from kwebui import KApp
from kwebui.editor import load_layout

# Next to this file, not relative to the working directory -- the example
# has to work whether it's run as `python examples/edit_mode_demo.py` or
# from inside examples/.
LAYOUT = Path(__file__).with_name("edit_mode_demo.layout.json")


class EditModeDemo(KApp):
    def build(self) -> None:
        self.text("Edit mode demo", size=26, bold=True)

        # Widgets built here in Python stay visible in edit mode but are
        # dimmed and not editable -- there is nowhere in the layout file
        # to write them back to. Everything below comes from the JSON.
        self.ui = load_layout(self, LAYOUT)

        # Wiring by id, the explicit alternative to naming the handler in
        # the layout file itself. Both work; this one is checked here so
        # the example runs whether or not the layout has been designed yet.
        if "save_button" in self.ui:
            self.ui["save_button"].update(on_click=self.on_save)

    # -- handlers the layout can name ------------------------------------

    def on_save(self) -> None:
        print("save clicked")
        if "status" in self.ui:
            self.ui["status"].set_text("Saved.")

    def on_reset(self) -> None:
        print("reset clicked")
        if "status" in self.ui:
            self.ui["status"].set_text("Reset.")


if __name__ == "__main__":
    EditModeDemo(
        title="Edit Mode Demo",
        edit_mode="--design" in sys.argv,
    ).run()
