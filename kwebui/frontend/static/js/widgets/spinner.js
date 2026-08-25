"use strict";

registerWidget("spinner", {
  props: ["data"],
  template: `
    <div class="sg-spinner" :data-active="data.props.active ? 'true' : 'false'">
      <span class="sg-spinner-ring"></span>
      <span>{{ label }}</span>
    </div>
  `,
  computed: {
    label() {
      const props = this.data.props;
      let text = props.text || "";
      if (props.show_time && props.elapsed !== null && props.elapsed !== undefined) {
        text += ` (${props.elapsed.toFixed(1)}s)`;
      }
      return text;
    },
  },
});
