"use strict";

registerWidget("slider", {
  props: ["data"],
  // Same focus-guard approach as textedit.js: the range input and its
  // live value label are synced imperatively so dragging isn't
  // interrupted by a server echo of the in-flight value.
  template: `
    <div class="sg-slider">
      <label v-show="data.props.label">{{ data.props.label }}</label>
      <div class="sg-slider-row">
        <input
          type="range"
          ref="input"
          :min="data.props.min_value"
          :max="data.props.max_value"
          :step="data.props.step"
          :disabled="data.enabled === false"
          @input="onInput"
        >
        <span ref="valueEl" class="sg-slider-value"></span>
      </div>
    </div>
  `,
  mounted() {
    this.syncValue();
  },
  updated() {
    this.syncValue();
  },
  methods: {
    onInput(event) {
      this.$refs.valueEl.textContent = event.target.value;
      sendEvent(this.data.id, "change", { value: parseFloat(event.target.value) });
    },
    syncValue() {
      const input = this.$refs.input;
      if (document.activeElement !== input) {
        input.value = this.data.props.value;
      }
      this.$refs.valueEl.textContent = this.data.props.value;
    },
  },
});
