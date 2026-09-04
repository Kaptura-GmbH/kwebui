// Generic keyboard-shortcut dispatch: any widget with a truthy
// `props.shortkey` (button, container, ...) gets a global "shortkey"
// event sent to it whenever the matching combo is pressed *and* that
// widget is currently visible on the page. The core/frontend never know
// what "shortkey" means for a given widget type -- same "core routes,
// plugin decides" split as every other event (see renderer.js/websocket.js)
// -- each plugin's own handle_event() interprets it (ButtonPlugin treats
// it like a click; ContainerPlugin calls on_keypress).
"use strict";

// "shift+ctrl+k" / "ctrl+shift+k" / "Ctrl+K" all normalize to the same
// {ctrl, alt, shift, meta, key} shape -- modifier order and case in the
// Python-side string never matter.
function parseShortkey(shortkey) {
  const parts = shortkey
    .toLowerCase()
    .split("+")
    .map((p) => p.trim())
    .filter(Boolean);
  return {
    key: parts[parts.length - 1],
    ctrl: parts.includes("ctrl") || parts.includes("control"),
    alt: parts.includes("alt"),
    shift: parts.includes("shift"),
    meta: parts.includes("meta") || parts.includes("cmd") || parts.includes("command"),
  };
}

// Exact match on every modifier (not "contains") -- otherwise a bare "k"
// shortkey would also fire while the user holds ctrl/alt for something
// else entirely.
function eventMatchesShortkey(event, shortkey) {
  const parsed = parseShortkey(shortkey);
  return (
    event.key.toLowerCase() === parsed.key &&
    event.ctrlKey === parsed.ctrl &&
    event.altKey === parsed.alt &&
    event.shiftKey === parsed.shift &&
    event.metaKey === parsed.meta
  );
}

function collectShortkeyWidgets(list, out) {
  for (const widget of list) {
    if (widget.props && widget.props.shortkey) out.push(widget);
    if (widget.children) collectShortkeyWidgets(widget.children, out);
  }
}

// Real DOM visibility, not a walk of the reactive tree's own `visible`
// flags -- a widget's root element already gets `display: none` (see
// renderer.js's nodeStyle) the instant it or any ancestor is hidden, so
// checking the actual rendered element for free handles "this container
// is hidden" cascading to every widget inside it, with no need to also
// walk parent widgets by hand. checkVisibility() (where available) is
// preferred over the older offsetParent!==null trick because the latter
// also (incorrectly, for this purpose) reports false for anything
// position:fixed, e.g. a widget inside .sg-toast/.sg-sidebar.
function isWidgetVisible(id) {
  const el = document.querySelector(`[data-widget-id="${id}"]`);
  if (!el) return false;
  return el.checkVisibility ? el.checkVisibility() : el.offsetParent !== null;
}

function isTypingTarget(el) {
  if (!el) return false;
  return el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable;
}

document.addEventListener("keydown", (event) => {
  const widgets = [];
  collectShortkeyWidgets(state.widgets, widgets);
  if (widgets.length === 0) return;

  const typing = isTypingTarget(document.activeElement);
  for (const widget of widgets) {
    if (widget.enabled === false) continue;
    if (!eventMatchesShortkey(event, widget.props.shortkey)) continue;

    const parsed = parseShortkey(widget.props.shortkey);
    // Bare/shift-only combos would hijack normal typing (e.g. a "k"
    // shortkey firing on every letter "k" typed into a textedit) --
    // suppress those specifically while a text field has focus. A combo
    // that also holds ctrl/alt/meta is rarely meaningful as literal text
    // input, so those still fire even while typing (the same convention
    // most desktop/web apps use for e.g. a "Ctrl+K" command shortcut).
    if (typing && !parsed.ctrl && !parsed.alt && !parsed.meta) continue;

    if (!isWidgetVisible(widget.id)) continue;

    event.preventDefault();
    sendEvent(widget.id, "shortkey");
  }
});
