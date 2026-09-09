// The single WebSocket connection: receives render patches, sends events.
// Mutates the reactive `state` from core.js -- Vue handles turning that
// into DOM changes, so this file never touches the DOM itself (except
// for the theme stylesheet swap, which is outside Vue's render tree).
"use strict";

// The run_id of the server process this page was first rendered against
// (see KApp.run_id). Null until the first "init" arrives.
let knownRunId = null;

// Must match SUPERSEDED_CLOSE_CODE in websocket.py: this tab was
// deliberately replaced by a newer one (KApp(single_session=True)), as
// opposed to having lost the server.
const SUPERSEDED_CLOSE_CODE = 4001;

// Direct DOM, deliberately outside Vue's render tree -- same reasoning as
// the theme stylesheet swap below: this has to keep working regardless of
// what the widget tree is doing, including while the connection carrying
// that tree is dead.
function showDisconnected(message) {
  const badge = document.getElementById("connection-status");
  if (!badge) return;
  badge.textContent = message;
  badge.hidden = false;
}

function hideDisconnected() {
  const badge = document.getElementById("connection-status");
  if (badge) badge.hidden = true;
}

// This tab was replaced by a newer one and is never coming back (only
// a reload can claim the app again), so leave it genuinely inert rather
// than merely badged: the badge alone still leaves a page that looks
// clickable, and -- more importantly -- an imagestream's <img> would go
// on pulling MJPEG frames over its own HTTP connection, which the closed
// WebSocket does nothing to stop.
function markSuperseded() {
  // Widgets that hold a live resource watch this and release it -- see
  // imagestream.js, which freezes on its last frame and drops the stream.
  state.superseded = true;
  // Nothing can be delivered any more, so make outgoing events a no-op
  // instead of letting them throw on the closed socket.
  sendEvent = () => {};
  // Visual + interaction cue, applied here rather than through Vue for
  // the same reason as the badge: it has to hold regardless of what the
  // widget tree does.
  document.body.classList.add("sg-superseded");
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
      showDisconnected("Disconnected — opened in another tab. Reload to use it here.");
      markSuperseded();
      return;
    }
    showDisconnected("Disconnected — reconnecting…");
    setTimeout(connect, 1000);
  });

  return ws;
}
