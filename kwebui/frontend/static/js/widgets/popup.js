"use strict";

// Built on the native <dialog> element rather than a hand-rolled overlay --
// Vue itself has no modal component, and <dialog>/showModal() is the
// platform's equivalent: focus trap, ::backdrop dimming, and Escape-to-
// cancel all come for free (see decisions.md).
registerWidget("popup", {
  props: ["data"],
  template: `
    <dialog ref="dialog" class="sg-popup" @cancel="onCancel">
      <p v-if="data.props.title" class="sg-popup-title">{{ data.props.title }}</p>
      <p class="sg-popup-message">{{ data.props.message }}</p>
      <div class="sg-popup-buttons">
        <button
          v-for="btn in data.props.buttons"
          :key="btn"
          type="button"
          :class="{ 'sg-popup-btn-primary': btn === 'ok' || btn === 'yes' }"
          @click="answer(btn)"
        >{{ label(btn) }}</button>
      </div>
    </dialog>
  `,
  mounted() {
    this.$refs.dialog.showModal();
  },
  methods: {
    label(btn) {
      return { ok: "OK", cancel: "Cancel", yes: "Yes", no: "No" }[btn] || btn;
    },
    answer(btn) {
      sendEvent(this.data.id, "answer", { answer: btn });
      this.$refs.dialog.close();
    },
    // The native Escape key fires "cancel" before closing -- only let it
    // through when Cancel is actually one of this popup's buttons, so an
    // ok-only or yes/no popup can't be dismissed without an explicit answer.
    onCancel(event) {
      if (this.data.props.buttons.includes("cancel")) {
        this.answer("cancel");
      } else {
        event.preventDefault();
      }
    },
  },
});
