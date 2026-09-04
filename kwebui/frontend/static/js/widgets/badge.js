"use strict";

registerWidget("badge", {
  props: ["data"],
  computed: {
    colorClass() {
      const color = this.data.props.color;
      return color ? `sg-badge-${color}` : "";
    },
  },
  template: `
    <span class="sg-badge" :class="colorClass">
      <span v-if="data.props.icon">{{ data.props.icon }}</span>
      <span>{{ data.props.text }}</span>
    </span>
  `,
});
