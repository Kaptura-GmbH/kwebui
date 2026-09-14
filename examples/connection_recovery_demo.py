"""Demonstrates a real, fixed bug: a broadcast failing to reach one
tab's socket used to crash that tab's *own* connection with an uncaught
RuntimeError -- silently, with no close frame ever reaching the browser
-- leaving it stuck (every click going nowhere) until a full page
reload. See decisions.md's entry on `_safe_send`/`Session.request_close`
for the fix and the two independent bug reports that led to it. Run
with:

    python examples/connection_recovery_demo.py

Then:
    1. Open the printed URL in TWO separate browser tabs, A and B.
    2. In tab A, click "Increment" a couple of times -- both tabs share
       one counter, so B's count updates too (this is kwebui's shared
       broadcast model; note this demo passes single_session=False so
       both tabs can stay live at once -- see the Session model section
       of docs/user-guide.md for why that isn't the default).
    3. In tab B, click "Make tab A's connection go silently dead". This
       forces tab A's *next* broadcast-send to fail with the exact
       OSError Starlette's own WebSocket raises for a genuinely dead
       peer -- a closed laptop lid, a dropped wifi connection -- without
       needing a second physical machine to demonstrate it.
    4. In tab A, click "Increment" again, and watch the small badge in
       the top-right corner. It should read "Disconnected --
       reconnecting..." for well under a second, then clear -- and the
       click you just made (or the very next one) goes through
       normally. Nothing needs reloading.

Before the fix, step 4 looked identical up to the badge -- but the
badge's own reconnect attempt raced into the very crash this simulates
being fixed, and every further click in tab A went silently nowhere
until the page was reloaded by hand. If you want to see that failure
mode for comparison, `git stash` this repo's `kwebui/app.py` and
`kwebui/websocket.py` changes from the fix's commit and rerun.
"""

from __future__ import annotations

from kwebui import KApp


class ConnectionRecoveryDemo(KApp):
    def build(self) -> None:
        self.text("Connection recovery demo", size=24, bold=True)
        self.text(
            "Open this page in two tabs. See this file's docstring for "
            "the full walkthrough.",
            color="#6b7280",
        )

        self.n = 0
        self.counter = self.text(f"count: {self.n}", size=20, bold=True)
        self.button("Increment", on_click=self.increment)

        self.status = self.text("", color="#6b7280")
        self.button(
            "Make tab A's connection go silently dead",
            on_click=self.simulate_dead_peer,
            color="#dc2626",
            text_color="white",
        )

    def increment(self) -> None:
        self.n += 1
        self.counter.set_text(f"count: {self.n}")

    def simulate_dead_peer(self) -> None:
        """Forces every *other* connected tab's next broadcast-send to
        fail with OSError -- exactly what Starlette's own WebSocket
        raises when the underlying socket is genuinely gone (a closed
        laptop lid, a dropped wifi connection, ...). This reaches into
        Starlette's WebSocket internals (`_send`) purely to make that
        one failure mode reproducible on demand from a single machine;
        a real app never needs to do this itself -- it's here only to
        demonstrate kwebui's own recovery from it.
        """
        me = self.session
        poisoned = 0
        for session in list(self._sessions):
            if session is me:
                continue
            real_send = session.websocket._send

            async def flaky_send(message, _real=real_send):
                if message.get("type") == "websocket.send":
                    raise OSError("Broken pipe (simulated dead peer)")
                return await _real(message)

            session.websocket._send = flaky_send
            poisoned += 1

        if poisoned == 0:
            self.status.set_text("No other tab is connected right now -- open a second one first.")
            return

        self.status.set_text(
            f"Poisoned {poisoned} other tab(s). Click Increment in that tab now -- "
            f"it should recover on its own within about a second."
        )
        # This broadcast is what actually *triggers* the forced failure
        # above -- it's the send attempt that hits the poisoned tab(s).
        self.increment()


if __name__ == "__main__":
    # single_session=False: this demo needs two tabs alive at once. Most
    # apps want the default (True) -- see docs/user-guide.md section 3.
    ConnectionRecoveryDemo(title="Connection Recovery Demo", single_session=False).run()
