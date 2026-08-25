"use strict";

registerWidget("sidebar", {
  props: ["data"],
  // This component has two root nodes (the sidebar div and a teleported
  // button), so Vue can't automatically fall through attrs like
  // data-widget-id/style onto "the" root -- inheritAttrs: false plus an
  // explicit v-bind="$attrs" puts them on the sidebar div ourselves,
  // exactly where they belong.
  inheritAttrs: false,
  // The collapse toggle is teleported to <body>, outside the sidebar's
  // own box, so it stays clickable and visible regardless of how the
  // sidebar itself is hidden when collapsed (translateX off-screen).
  template: `
    <div class="sg-sidebar" v-bind="$attrs" :data-collapsed="collapsed ? 'true' : 'false'">
      <slot></slot>
    </div>
    <Teleport to="body" v-if="collapsible">
      <button type="button" class="sg-sidebar-toggle" :style="{ left: toggleLeft }" @click="toggle">
        {{ collapsed ? "›" : "‹" }}
      </button>
    </Teleport>
  `,
  data() {
    return { collapsed: false };
  },
  computed: {
    // collapsible defaults to true (matches SidebarPlugin.create's Python
    // default) so widgets serialized before this feature existed, or a
    // frontend/backend version mismatch, still behave as before.
    collapsible() {
      return this.data.props.collapsible !== false;
    },
    toggleLeft() {
      return this.collapsed ? "0.75rem" : "calc(var(--sg-sidebar-width) + 0.75rem)";
    },
  },
  mounted() {
    document.body.classList.add("sg-has-sidebar");
  },
  beforeUnmount() {
    document.body.classList.remove("sg-has-sidebar", "sg-sidebar-collapsed");
  },
  methods: {
    toggle() {
      if (!this.collapsible) return;
      this.collapsed = !this.collapsed;
      document.body.classList.toggle("sg-sidebar-collapsed", this.collapsed);
    },
  },
});
