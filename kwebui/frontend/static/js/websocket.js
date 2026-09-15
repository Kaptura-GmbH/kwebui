// The single WebSocket connection: receives render patches, sends events.
// Mutates the reactive `state` from core.js -- Vue handles turning that
// into DOM changes, so this file never touches the DOM itself (except
// for the theme stylesheet swap, which is outside Vue's render tree).
"use strict";

// The run_id of the server process this page was first rendered against
// (see KApp.run_id). Null until the first "init" arrives.
let knownRunId = null;

// Must match the close codes of the same name in websocket.py: this tab
// was deliberately, permanently disconnected on purpose -- either
// replaced by a newer one (KApp(single_session=True)) or the app
// stopping via KApp.exit()/Ctrl+C/SIGTERM -- as opposed to having lost
// the server (an ordinary close, which does keep retrying).
const SUPERSEDED_CLOSE_CODE = 4001;
const SHUTDOWN_CLOSE_CODE = 4002;

// Direct DOM, deliberately outside Vue's render tree -- same reasoning as
// the theme stylesheet swap below: this has to keep working regardless of
// what the widget tree is doing, including while the connection carrying
// that tree is dead.
function showDisconnected(message) {
  const badge = document.getElementById("connection-status");
  if (!badge) return;
  // Only the text span's content, never the badge's own innerHTML/
  // textContent -- overwriting the whole badge would also wipe out the
  // reload button markTerminal() below may have just revealed.
  document.getElementById("connection-status-text").textContent = message;
  badge.hidden = false;
}

function hideDisconnected() {
  const badge = document.getElementById("connection-status");
  if (badge) badge.hidden = true;
}

// KApp(reload_button=...) (default True) -- index.html renders this as a
// data attribute since it's a fixed, per-app setting rather than
// something that could change per connection, so no server round trip
// is needed to know it before the very first close event that might
// want to show the button.
function reloadButtonEnabled() {
  const badge = document.getElementById("connection-status");
  return !!badge && badge.dataset.reloadButton !== "false";
}

// This tab is never coming back on its own -- either a newer tab
// replaced it (only a reload can claim the app back), or the app itself
// stopped (nothing to reload back to) -- so leave it genuinely inert
// rather than merely badged: the badge alone still leaves a page that
// looks clickable, and -- more importantly -- an imagestream's <img>
// would go on pulling MJPEG frames over its own HTTP connection, which
// the closed WebSocket does nothing to stop.
function markTerminal(message) {
  showDisconnected(message);
  // A terminal tab needs a *manual* way back -- unlike an ordinary
  // reconnecting close, nothing here will ever retry on its own (see the
  // close handler below for why). Reloading is that way back regardless
  // of which terminal reason applies: it reclaims a superseded session,
  // or reconnects once a stopped app is running again. Opt-out via
  // KApp(reload_button=False) for a display nobody is meant to touch.
  if (reloadButtonEnabled()) {
    document.getElementById("connection-status-reload").hidden = false;
  }
  // Widgets that hold a live resource watch this and release it -- see
  // imagestream.js, which freezes on its last frame and drops the stream.
  state.terminated = true;
  // Nothing can be delivered any more, so make outgoing events a no-op
  // instead of letting them throw on the closed socket.
  sendEvent = () => {};
  // Visual + interaction cue, applied here rather than through Vue for
  // the same reason as the badge: it has to hold regardless of what the
  // widget tree does.
  document.body.classList.add("sg-terminated");
}

function connect() {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${protocol}//${location.host}/ws`);

  sendEvent = (widgetId, type, payload) => {
    ws.send(JSON.stringify({ widget_id: widgetId, type, payload: payload || {} }));
  };

  ws.addEventListener("open", () => hideDisconnected());

  ws.addEventListener("message", (message) => {
    const data = JSON.parse(message.data);
    if (data.op === "init") {
      // A different run_id means this is a different server process than
      // the one this page was rendered against -- i.e. the app was
      // stopped and started again while this tab stayed open, and the new
      // run happened to claim the same port. Patching the existing page
      // would leave it half-broken (interactive again, but with e.g. a
      // permanently frozen imagestream, since the <img> never re-requests
      // /stream/). Reload instead, so the tab becomes an honestly fresh
      // page of the new run. run_id is fixed per process, so the reloaded
      // page adopts the new id as its own and never loops.
      if (knownRunId !== null && data.run_id !== knownRunId) {
        location.reload();
        return;
      }
      knownRunId = data.run_id;
      state.widgets = data.widgets;
    } else if (data.op === "update") {
      applyUpdate(data.widget);
    } else if (data.op === "theme") {
      document.getElementById("theme-stylesheet").href = `/themes/${data.name}.css`;
    } else if (data.op === "focus") {
      focusWidget(data.widget_id);
    } else if (data.op === "remove") {
      removeWidget(data.widget_id);
    }
  });

  ws.addEventListener("close", (event) => {
    if (event.code === SUPERSEDED_CLOSE_CODE) {
      // Deliberately terminal: no reconnect. Retrying here would connect
      // again, which in single_session mode supersedes the newer tab,
      // whose own retry would then supersede this one -- an endless
      // once-a-second tug of war between two tabs. Reloading is the
      // user's explicit way to claim the app back.
      markTerminal("Disconnected — opened in another tab. Reload to use it here.");
      return;
    }
    if (event.code === SHUTDOWN_CLOSE_CODE) {
      // Also deliberately terminal, for a different reason: the process
      // itself is gone (KApp.exit() / Ctrl+C / SIGTERM), so retrying
      // would just be a silent, endless loop of connection-refused
      // errors against a server that isn't coming back.
      markTerminal("Disconnected — the app has stopped.");
      return;
    }
    showDisconnected("Disconnected — reconnecting…");
    setTimeout(connect, 1000);
  });

  return ws;
}

// Wired once, unconditionally -- the button stays hidden until
// markTerminal() reveals it (and never at all if reload_button=False, in
// which case this listener simply never fires). Bound here rather than
// inside markTerminal() so a second terminal event on the same page
// (can't currently happen -- there's no path back from "terminated" --
// but kept this way on purpose) can never attach a duplicate listener.
document.getElementById("connection-status-reload")?.addEventListener("click", () => location.reload());
