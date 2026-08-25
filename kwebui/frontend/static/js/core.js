// The reactive widget tree plus the frontend "plugin registry": each file
// in js/widgets/ calls registerWidget(type, componentDefinition) to plug
// itself in as a Vue component. This file only knows that widget
// components exist -- never which widget types are registered.
"use strict";

// Single source of truth for the whole page. websocket.js mutates this in
// response to "init"/"update" messages; Vue's reactivity re-renders
// whatever changed. Nothing here builds or patches DOM directly -- that's
// entirely Vue's job now, driven by WidgetNode in renderer.js.
const state = Vue.reactive({ widgets: [] });

/** Find a widget by id anywhere in the tree (top-level or nested inside
 * children) and merge new data onto it in place, so Vue's reactivity
 * picks up the change. Returns false if no matching widget exists yet. */
function findAndPatch(list, data) {
  for (const widget of list) {
    if (widget.id === data.id) {
      Object.assign(widget, data);
      return true;
    }
    if (widget.children && findAndPatch(widget.children, data)) return true;
  }
  return false;
}

/** Apply an "update" message: patch the widget if already known, or add
 * it fresh if this is the first the browser has heard of it (a widget
 * created from inside a callback after the initial page load). */
function applyUpdate(data) {
  if (!findAndPatch(state.widgets, data)) {
    state.widgets.push(data);
  }
}

/** Remove a widget anywhere in the tree, top-level or nested inside a
 * container's children (toasts remove themselves this way once their
 * timeout elapses -- see toast.js -- and the server does the same for
 * one-shot widgets like an answered popup -- see websocket.js). */
function removeWidget(id) {
  removeFromList(state.widgets, id);
}

function removeFromList(list, id) {
  const index = list.findIndex((widget) => widget.id === id);
  if (index !== -1) {
    list.splice(index, 1);
    return true;
  }
  return list.some((widget) => widget.children && removeFromList(widget.children, id));
}

/** Send keyboard focus to a widget's underlying input element, wherever
 * it is in the DOM. Generic over widget type: rather than every widget
 * component wiring up its own focus handling, this looks for whatever
 * the widget itself would naturally receive focus on (an <input>,
 * <textarea>, <select>, or <button>) inside the element the wire
 * protocol already tags with data-widget-id -- widgets with no such
 * element (text, image, ...) are simply not focusable, silently. */
function focusWidget(id) {
  const root = document.querySelector(`[data-widget-id="${id}"]`);
  if (!root) return;
  const focusable = root.matches("input, textarea, select, button, [tabindex]")
    ? root
    : root.querySelector("input, textarea, select, button, [tabindex]");
  if (focusable) focusable.focus();
}

// Replaced with a real function once the WebSocket connects (see
// websocket.js) -- a plain module-global rather than passed as an
// argument through every component, since there is only ever one
// connection for the whole app.
let sendEvent = () => {};

const vueApp = Vue.createApp({
  template: `<widget-node v-for="widget in state.widgets" :key="widget.id" :data="widget" />`,
  data() {
    return { state };
  },
});

const REGISTERED_WIDGET_TYPES = new Set();

// Registered under a "kw-" prefixed name, not the raw type, because some
// widget type names (button, text, html, image) collide with native or
// SVG-reserved HTML tag names -- Vue warns about (and doesn't reliably
// support) global components registered under those.
function registerWidget(type, definition) {
  REGISTERED_WIDGET_TYPES.add(type);
  vueApp.component(`kw-${type}`, definition);
}
