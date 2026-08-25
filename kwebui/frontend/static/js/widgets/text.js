"use strict";

registerWidget("text", {
  props: ["data"],
  template: `<p class="sg-text" :style="textStyle">{{ data.props.text }}</p>`,
  computed: {
    textStyle() {
      const props = this.data.props;
      return {
        fontSize: `${props.size}px`,
        color: props.color,
        fontWeight: props.bold ? "bold" : "normal",
        fontStyle: props.italic ? "italic" : "normal",
        textAlign: props.align,
      };
    },
  },
});
