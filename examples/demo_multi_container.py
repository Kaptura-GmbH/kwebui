"""Two panels, each driven by its own background thread. Run with:

    python examples/demo_multi_container.py

Panel 1 starts a slow counting thread when you click its button. Clicking
"Go to Panel 2" switches panels immediately, but the thread keeps running
and keeps ticking its own text widget in the background -- switch back and
you'll see it kept going the whole time.

Panel 2 starts its own counting thread the moment it becomes visible, and
stops that thread automatically the moment you navigate away from it -- no
manual "stop" button needed.

Both threads are fully independent, so switching back and forth between
panels never conflicts with either one.
"""
import threading
import time

from kwebui import KApp


class Demo(KApp):
    def build(self) -> None:
        self.text("Independent Background Threads", size=24, bold=True)

        self.panel1_running = False
        self.panel2_stop: threading.Event | None = None

        self.container_1()
        self.container_2()
        self.panel2.hide()

    def container_1(self) -> None:
        self.panel1 = self.container(caption="Panel 1 -- keeps running after you leave", stretch=True)
        self.panel1_status = self.panel1.text("Not started.")
        self.panel1.button("Start delay task (8s)", on_click=lambda: self.start_panel1_task())
        self.panel1.button("Go to Panel 2", on_click=lambda: self.goto_panel2())

    def container_2(self) -> None:
        self.panel2 = self.container(caption="Panel 2 -- stops as soon as you leave", stretch=True)
        self.panel2_status = self.panel2.text("")
        self.panel2.button("Go to Panel 1", on_click=lambda: self.goto_panel1())

    def goto_panel2(self) -> None:
        self.panel1.hide()
        self.panel2.show()
        self.start_panel2_task()

    def goto_panel1(self) -> None:
        self.stop_panel2_task()
        self.panel2.hide()
        self.panel1.show()

    def start_panel1_task(self) -> None:
        if self.panel1_running:
            return
        self.panel1_running = True
        threading.Thread(target=self._panel1_loop, daemon=True).start()

    def _panel1_loop(self) -> None:
        for i in range(1, 9):
            time.sleep(1)
            self.panel1_status.set_text(f"Tick {i}/8 -- still running even off-screen")
        self.panel1_status.set_text("Done!")
        self.panel1_running = False

    def start_panel2_task(self) -> None:
        stop_event = threading.Event()
        self.panel2_stop = stop_event
        threading.Thread(target=self._panel2_loop, args=(stop_event,), daemon=True).start()

    def stop_panel2_task(self) -> None:
        if self.panel2_stop is not None:
            self.panel2_stop.set()
            self.panel2_stop = None

    def _panel2_loop(self, stop_event: threading.Event) -> None:
        n = 0
        while not stop_event.is_set():
            n += 1
            self.panel2_status.set_text(f"Ticking... {n}")
            time.sleep(0.5)
        self.panel2_status.set_text("Stopped.")


if __name__ == "__main__":
    Demo(title="Multi Container Threads Demo").run()
