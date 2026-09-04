"""Every built-in widget in one app. Run with:

    python examples/showcase.py

Then open the printed URL (default http://127.0.0.1:8701, or the next
free port after it) in a browser.
"""

from pathlib import Path
import time

from kwebui import KApp

ASSET = Path(__file__).parent / "assets" / "sample.png"

WORKFLOW_TASKS = [
    {"id": 1, "title": "Task 1", "status": "completed"},
    {"id": 2, "title": "Task 2", "status": "in-progress"},
    {"id": 3, "title": "Task 3", "status": "pending"},
    {"id": 4, "title": "Task 4", "status": "pending"},
]

def on_enter(value: str) -> None:
    print("on_enter fired with:", value)
class Showcase(KApp):
    def build(self) -> None:
        # topbar() is called first so it's the first thing on the page --
        # combined with its default sticky=True, it stays pinned to the
        # viewport top as the rest of the page scrolls underneath it.
        bar = self.topbar()
        self.tracker = bar.workflow_tracker(WORKFLOW_TASKS, on_select=self.on_tracker_select)

        sidebar = self.sidebar(collapsible=True)  # collapsible=True is the default; pass collapsible=False to pin it open
        sidebar.text("Navigation", size=18, bold=True)
        sidebar.button("Home", on_click=lambda: print("home clicked"))
        sidebar.button("Settings", on_click=lambda: print("settings clicked"))
        sidebar.text("Pinned open (collapsible=False) -- no collapse arrow.", color="#6b7280")

        self.text("kwebui Showcase", size=28, bold=True)
        self.text("Every built-in widget, wired to a Python callback.", color="#6b7280")

        
        self.button("Click Me", on_click=lambda: print("Clicked"))
        self.button("Delete (color/text_color)", on_click=lambda: print("Deleted"), color="red", text_color="white")
        self.button("Custom (purple)", on_click=lambda: print("Custom"), color="purple")

        self.checkbox("Enable feature", on_change=lambda checked: print("checkbox:", checked))

        self.name = self.textedit("Name", placeholder="Jane Doe")
        self.button("Hide btn", on_click=lambda: self.name.hide())
        self.button("Highlight Name", on_click=self.toggle_name_highlight)
        self.button("Focus Name", on_click=lambda: self.name.focus())
        self.textedit("Bio", multiline=True, placeholder="Tell us about yourself")
        self.textedit("Password", password=True)
        self.enter_result = self.empty()
        self.textedit(
            "Device ID",
            placeholder="Type an ID, then press Enter",
            on_enter=lambda v: self.enter_result.text(f"on_enter fired with: {v!r}", color="#2563eb"),
        )

        self.text("Hide, show, remove", size=18, bold=True)
        self.removable = self.text("This widget can be hidden or removed.", color="#2563eb")
        self.button("Hide", on_click=self.removable.hide)
        self.button("Show", on_click=self.removable.show)
        self.button("Remove permanently", on_click=lambda: self.removable.remove())

        self.text("Enable, disable", size=18, bold=True)
        self.disableable_button = self.button("Click me", on_click=lambda: print("clicked"))
        self.disableable_edit = self.textedit("Disableable field", placeholder="type here")
        self.button("Disable button + field", on_click=self.disable_demo_widgets)
        self.button("Enable button + field", on_click=self.enable_demo_widgets)

        self.text("Keyboard shortcuts", size=18, bold=True)
        self.text("Press 'g' anywhere on the page (not while typing in a field).", color="#6b7280")
        self.button("Greet (shortkey='g')", on_click=self.greet, shortkey="g")
        self.shortkey_status = self.text("Container shortkey not pressed yet.", color="#6b7280")
        shortkey_panel = self.container(
            border=True, caption="ctrl+j while this panel is visible",
            shortkey="ctrl+j", on_keypress=lambda: self.shortkey_status.set_text("ctrl+j pressed!"),
        )
        shortkey_panel.text("This panel's on_keypress only fires while the panel itself is shown.")
        self.button("Hide this panel", on_click=shortkey_panel.hide)
        self.button("Show this panel", on_click=shortkey_panel.show)

        self.listbox(["Apples", "Bananas", "Cherries"], on_select=lambda item: print("selected:", item))

        self.progress = self.progressbar(50)
        self.progressbar(0, indeterminate=True)

        self.volume = self.slider("Volume", min_value=0, max_value=100, value=50, on_change=self.on_volume)
        self.text1 = self.text(f"Volume is  {self.volume.props['value']:.0f}")

        self.image(str(ASSET), stretch=True)

        self.html("<strong>Raw HTML:</strong> <em>this text</em> came from <code>app.html(...)</code>.")

        self.status = self.empty()
        self.status.text("Waiting for input...", color="#6b7280")

        self.text(f"Layout with columns()", size=18, bold=True)
        left, right = self.columns(2)
        left.text("Left column")
        left.button("Left button", on_click=lambda: print("left clicked"))
        right.text("Right column")
        right.button("Right button", on_click=lambda: print("right clicked"))

        self.text("columns([0.1, 0.2, 0.7]) -- relative widths, weights sum to 1", size=18, bold=True)
        narrow, medium, wide = self.columns([0.1, 0.2, 0.7])
        narrow.text("10%")
        medium.text("20%")
        wide.text("70%")

        self.text("Status banners", size=18, bold=True)
        self.success("This is a success message.")
        self.info("This is an info message.")
        self.warning("This is a warning message.")
        self.error("This is an error message.")

        self.text("Badges", size=18, bold=True)
        self.badge("New")
        self.badge("Beta", color="info")
        self.badge("Active", icon="✅", color="success")
        self.badge("Deprecated", color="warning")
        self.badge("Failed", icon="🚫", color="error")

        self.text("File upload", size=18, bold=True)
        self.file_uploader("Upload a file", on_upload=self.on_upload)

        self.text("JSON viewer", size=18, bold=True)
        self.json({"framework": "kwebui", "widgets": ["text", "button", "slider"], "version": 1})

        self.button("Greet", on_click=self.greet)
        self.button("Toast", on_click=lambda: self.toast("Saved!", level="success"))
        self.button("Spinner demo", on_click=self.run_spinner_demo)
        self.button("Simulate work", on_click=self.simulate_work)

        self.text("Popups", size=18, bold=True)
        self.button("Popup: OK", on_click=lambda: self.popup("Saved.", kind="ok", on_return=self.on_popup_answer))
        self.button(
            "Popup: Yes/No",
            on_click=lambda: self.popup(
                "Enable notifications?", kind="yesno", on_return=self.on_popup_answer
            ),
        )
        self.button(
            "Popup: OK/Cancel",
            on_click=lambda: self.popup(
                "Proceed with deployment?", kind="okcancel", on_return=self.on_popup_answer
            ),
        )
        self.button(
            "Popup: Yes/No/Cancel",
            on_click=lambda: self.popup(
                "Save changes before closing?",
                title="Unsaved changes",
                kind="yesnocancel",
                on_return=self.on_popup_answer,
            ),
        )

        # A second, independent tracker instance (same starting data, its
        # own widget) just to show the vertical orientation side by side
        # with the topbar's horizontal one -- the buttons below only
        # affect self.tracker (the topbar one).
        self.text("Containers", size=18, bold=True)
        self.container().text("Default: bordered, rounded corners, sized to content.")
        self.container(border=False).text("border=False: no border at all.")
        self.container(border_roundness=False).text("border_roundness=False: square corners.")
        self.container(width=250).text("width=250: fixed-width box.")
        self.container(stretch=True).text("stretch=True: fills the parent's width.")
        self.container(caption="Settings").text("caption breaks the top border line, like a fieldset legend.")
        aligned = self.container(width=400, horizontal_alignment="center", caption="horizontal_alignment='center'")
        aligned.button("Centered button")
        panel = self.container(
            width=400, height=150, border=True,
            horizontal_alignment="center", vertical_alignment="center",
            caption="height=150, both alignments centered",
        )
        panel.button("A panel with a centered button")
        padded = self.container(
            width=300, caption="vertical_padding=16, horizontal_padding=40",
            vertical_padding=16, horizontal_padding=40,
        )
        padded.text("Breathing room around this text, instead of flush against the border.")
        row = self.container(direction="horizontal", caption="direction='horizontal': children side by side")
        row.text("test1")
        row.text("test2")
        flow = self.container(
            direction="horizontal", wrap=True, width=260,
            caption="direction='horizontal', wrap=True",
        )
        for label in ("New", "Beta", "Active", "Deprecated", "Failed"):
            flow.badge(label)
        self.hideable_container = self.container(caption="Hideable")
        self.hideable_container.text("This whole container can be hidden or shown.")
        self.button("Hide container", on_click=self.hideable_container.hide)
        self.button("Show container", on_click=self.hideable_container.show)

        self.text("Table", size=18, bold=True)
        self.table([
            {"name": "Alice", "role": "Engineer", "age": 30},
            {"name": "Bob", "role": "Designer", "age": 25},
            {"name": "Carol", "role": "Manager", "age": 42},
        ])
        self.table(
            {"name": ["Alice", "Bob"], "role": ["Engineer", "Designer"]},
            hide_header=True,
        )
        self.table(
            [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}],
            border=False,
            stretch=True,
        )

        self.text("Workflow tracker (vertical orientation)", size=18, bold=True)
        self.button("Advance workflow", on_click=self.advance_workflow)
        self.button("Mark current step as error", on_click=self.error_current_step)
        self.workflow_tracker(WORKFLOW_TASKS, orientation="vertical")

        self.set_theme("dark")

    def on_volume(self, value: float) -> None:
        print("volume:", value)
        self.text1.set_text(f"{value:.0f}")

    def on_upload(self, filename: str, data: bytes) -> None:
        print(f"uploaded {filename} ({len(data)} bytes)")

    def toggle_name_highlight(self) -> None:
        # highlight()/unhighlight() work on any widget, not just textedit --
        # this one passes no color, so it falls back to the active theme's
        # --sg-highlight variable (red by default).
        if self.name.highlighted:
            self.name.unhighlight()
        else:
            self.name.highlight()

    def disable_demo_widgets(self) -> None:
        # enable()/disable() work on any widget, not just button/textedit
        # -- see kwebui/widget.py.
        self.disableable_button.disable()
        self.disableable_edit.disable()

    def enable_demo_widgets(self) -> None:
        self.disableable_button.enable()
        self.disableable_edit.enable()

    def on_popup_answer(self, answer: str) -> None:
        self.toast(f"Popup answered: {answer}", level="info")

    def on_tracker_select(self, task_id: int) -> None:
        self.toast(f"Workflow step {task_id} clicked", level="info")

    def advance_workflow(self) -> None:
        tasks = self.tracker.props["tasks"]
        current = next((t for t in tasks if t["status"] == "in-progress"), None)
        if current is None:
            return
        self.tracker.set_task_status(current["id"], "completed")
        following = next((t for t in tasks if t["id"] == current["id"] + 1), None)
        if following is not None:
            self.tracker.set_task_status(following["id"], "in-progress")
        else:
            self.toast("Workflow complete!", level="success")

    def error_current_step(self) -> None:
        tasks = self.tracker.props["tasks"]
        current = next((t for t in tasks if t["status"] == "in-progress"), None)
        if current is not None:
            self.tracker.set_task_status(current["id"], "error", detail="Needs attention")

    def greet(self) -> None:
        self.status.text(f"Hello, {self.name.value or 'stranger'}!", color="#2563eb")
        self.progress.set_value(min(100.0, self.progress.props["value"] + 10))
        print("Greetings!")

    def run_spinner_demo(self) -> None:
        with self.spinner("Working...", show_time=True):
            self.text("This text is shown while the spinner is active.")
            time.sleep(5)

    def simulate_work(self) -> None:
        # Callbacks are dispatched off the event loop (see
        # App._dispatch_event), so this blocking sleep doesn't freeze
        # broadcasting to other connected browsers -- no manual
        # threading needed here.
        with self.spinner("Simulating work...", show_time=True):
            time.sleep(1.5)
        self.toast("Work finished!", level="success")


if __name__ == "__main__":
    Showcase(title="kwebui Showcase", width=500).run()
