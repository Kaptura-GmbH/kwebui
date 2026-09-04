// The generic recursive renderer: knows the *shape* of a widget (id,
// type, props, style, children) but never what a specific type means.
// Replaces the old buildWidgetElement/mountWidget/updateWidget/
// rebuildChildren quartet -- Vue's own reactivity + virtual DOM diffing
// now does what those hand-written functions used to do by hand.
"use strict";

vueApp.component("widget-node", {
  name: "WidgetNode",
  props: ["data"],
  computed: {
    // Falls back to a silent placeholder (and a console error) for a
    // widget type with no registered component, instead of crashing the
    // whole render -- mirrors the old buildWidgetElement's behavior.
    componentName() {
      return REGISTERED_WIDGET_TYPES.has(this.data.type) ? `kw-${this.data.type}` : "unknown-widget";
    },
    // Per-widget highlight_color overrides the theme's --sg-highlight
    // variable (see base.css) only for this element, via an inline
    // custom property -- leaving it unset falls through to the theme.
    // hide()/show() are generic across every widget type (see widget.py),
    // so the "hidden" -> display:none translation lives here once rather
    // than in each widget's own component.
    nodeStyle() {
      let style =
        this.data.highlighted && this.data.highlight_color
          ? { ...this.data.style, "--sg-highlight-color": this.data.highlight_color }
          : this.data.style;
      // Generic across every widget type, same reasoning as visible's
      // display:none above: dims it and blocks mouse interaction (click,
      // hover) with no per-widget code needed. Mouse-only, though --
      // pointer-events:none can't stop keyboard interaction with an
      // already-focused/tabbed-to native control, so the widgets with a
      // real <input>/<select>/<textarea>/<button> additionally bind that
      // element's own `disabled` attribute themselves (see e.g.
      // textedit.js) for full keyboard robustness. Either way,
      // KApp._dispatch_event is the actual, authoritative enforcement --
      // this is purely the visual/UX cue.
      if (this.data.enabled === false) {
        style = { ...style, opacity: 0.5, pointerEvents: "none", cursor: "not-allowed" };
      }
      if (this.data.visible === false) return { ...style, display: "none" };
      return style;
    },
  },
  template: `
    <component
      :is="componentName"
      :data="data"
      :data-widget-id="data.id"
      :data-widget-type="data.type"
      :data-highlighted="data.highlighted ? 'true' : null"
      :style="nodeStyle"
    >
      <widget-node v-for="child in data.children || []" :key="child.id" :data="child" />
    </component>
  `,
});

vueApp.component("unknown-widget", {
  props: ["data"],
  template: `<span style="display: none"></span>`,
  created() {
    console.error(`No frontend renderer registered for widget type "${this.data.type}"`);
  },
});
