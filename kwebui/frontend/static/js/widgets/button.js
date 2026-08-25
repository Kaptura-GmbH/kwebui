"use strict";

registerWidget("button", {
  props: ["data"],
  computed: {
    // Both default to unset, which leaves the CSS class's own
    // background/color (the theme's --sg-accent/--sg-accent-fg) in
    // effect -- same "omit the key entirely rather than pass a
    // theme-derived default" pattern as container's alignStyle, so a
    // button with neither prop set renders byte-identical to before
    // these existed.
    colorStyle() {
      const style = {};
      if (this.data.props.color) style.backgroundColor = this.data.props.color;
      if (this.data.props.text_color) style.color = this.data.props.text_color;
      return style;
    },
  },
  template: `
    <button type="button" class="sg-button" :style="colorStyle" :disabled="data.props.enabled === false" @click="onClick">
      {{ data.props.text }}
    </button>
  `,
  methods: {
    onClick() {
      sendEvent(this.data.id, "click");
    },
  },
});
