"use strict";

// A structural container with no visuals of its own -- its children (the
// current slot content) are rendered generically by renderer.js's
// widget-node, which passes them in as this component's default slot.
registerWidget("empty", {
  props: ["data"],
  template: `<div class="sg-empty"><slot></slot></div>`,
});
