// The single WebSocket connection: receives render patches, sends events.
// Mutates the reactive `state` from core.js -- Vue handles turning that
// into DOM changes, so this file never touches the DOM itself (except
// for the theme stylesheet swap, which is outside Vue's render tree).
"use strict";

function connect() {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${protocol}//${location.host}/ws`);

  sendEvent = (widgetId, type, payload) => {
    ws.send(JSON.stringify({ widget_id: widgetId, type, payload: payload || {} }));
  };

  ws.addEventListener("message", (message) => {
    const data = JSON.parse(message.data);
    if (data.op === "init") {
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

  ws.addEventListener("close", () => {
    setTimeout(connect, 1000);
  });

  return ws;
}
