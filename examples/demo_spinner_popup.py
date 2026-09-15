"""Automatic startup task in a spinner, then an on-demand short task
gated behind a yes/no popup confirmation. Run with:

    python examples/demo_spinner_popup.py

On load, a background thread immediately starts a 20s "task" while a
spinner shows progress. The button is enabled from the start -- clicking
it opens a popup, and answering "Yes" runs a second, short (2s) task in
its own spinner, in parallel with the still-running startup task. Each
task is its own thread with its own spinner and status text, so neither
blocks or overwrites the other.
"""
import threading
import time

from kwebui import KApp


class Demo(KApp):
    def build(self) -> None:
        self.text("Spinner + Popup Demo", size=24, bold=True)

        self.startup_spinner = self.spinner("Running startup task (20s)...", show_time=True)
        self.startup_status = self.text("")
        self.run_button = self.button("Run short task", on_click=self.ask_to_run)

        threading.Thread(target=self._startup_task, daemon=True).start()

    def _startup_task(self) -> None:
        with self.startup_spinner:
            time.sleep(20)
        self.startup_status.set_text("Startup task complete.")

    def ask_to_run(self) -> None:
        self.popup(
            "Run the short task now?",
            kind="yesno",
            on_return=self.on_confirm_answer,
        )

    def on_confirm_answer(self, answer: str) -> None:
        if answer != "yes":
            return
        threading.Thread(target=self._short_task, daemon=True).start()

    def _short_task(self) -> None:
        status = self.text("")
        with self.spinner("Running short task (2s)...", show_time=True):
            time.sleep(2)
        status.set_text("Short task complete.")


if __name__ == "__main__":
    Demo(title="Spinner + Popup Demo").run()
