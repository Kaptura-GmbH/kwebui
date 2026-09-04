"use strict";

registerWidget("textedit", {
  props: ["data"],
  // The field's value is synced imperatively (mounted/updated + a focus
  // check) rather than via a reactive :value binding, so an update
  // echoed back from the server never clobbers what the user is
  // currently typing.
  template: `
    <div class="sg-textedit">
      <label v-show="data.props.label">{{ data.props.label }}</label>
      <textarea
        v-if="data.props.multiline"
        ref="field"
        :placeholder="data.props.placeholder"
        :disabled="data.enabled === false"
        @input="onInput"
      ></textarea>
      <input
        v-else
        ref="field"
        :type="data.props.password ? 'password' : 'text'"
        :placeholder="data.props.placeholder"
        :disabled="data.enabled === false"
        @input="onInput"
        @keydown.enter="onEnter"
      >
    </div>
  `,
  // Enter only fires on_enter for the single-line input -- a multiline
  // textarea's Enter key means "insert a newline", not "submit".
  mounted() {
    this.syncValue();
  },
  updated() {
    this.syncValue();
  },
  methods: {
    onInput(event) {
      sendEvent(this.data.id, "change", { value: event.target.value });
    },
    onEnter(event) {
      sendEvent(this.data.id, "enter", { value: event.target.value });
    },
    syncValue() {
      const field = this.$refs.field;
      if (document.activeElement !== field) {
        field.value = this.data.props.value || "";
      }
    },
  },
});
