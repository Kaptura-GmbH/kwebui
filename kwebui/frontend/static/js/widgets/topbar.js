"use strict";

// Teleported to #topbar-root (a placeholder in index.html, positioned
// before #app-root) rather than rendered inline -- that makes it a true
// top-level layout region living directly under <body>, exactly like
// .sg-sidebar, so its width is a plain 100% of the viewport instead of
// having to break out of #app-root's centered max-width. Two root nodes
// (the Teleport's target content) means Vue can't auto-forward
// data-widget-id/style the way it does for a single-root component --
// inheritAttrs: false + manual v-bind="$attrs" does it explicitly, same
// fix sidebar.js already needed for the same reason (see its comment).
registerWidget("topbar", {
  props: ["data"],
  inheritAttrs: false,
  template: `
    <Teleport to="#topbar-root">
      <div class="sg-topbar" v-bind="$attrs" :class="{ 'sg-topbar-sticky': data.props.sticky !== false }">
        <slot></slot>
      </div>
    </Teleport>
  `,
});
