"use strict";

registerWidget("checkbox", {
  props: ["data"],
  template: `
    <label class="sg-checkbox">
      <input type="checkbox" :checked="!!data.props.checked" @change="onChange">
      <span>{{ data.props.label }}</span>
    </label>
  `,
  methods: {
    onChange(event) {
      sendEvent(this.data.id, "change", { checked: event.target.checked });
    },
  },
});
