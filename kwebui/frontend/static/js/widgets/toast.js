"use strict";

// Fire-and-forget: the browser removes it from the reactive tree itself
// after duration_ms, the Python side never hears about it (see toast.py).
registerWidget("toast", {
  props: ["data"],
  template: `
    <div :class="['sg-toast', 'sg-toast-' + data.props.level]" :style="{ top: topOffset }">
      {{ message }}
    </div>
  `,
  computed: {
    message() {
      return `${this.data.props.icon || ""} ${this.data.props.message}`.trim();
    },
    // Stack index = position among currently-visible toasts, so several
    // stack downward instead of overlapping.
    topOffset() {
      const toasts = state.widgets.filter((widget) => widget.type === "toast");
      const index = Math.max(toasts.findIndex((widget) => widget.id === this.data.id), 0);
      return `${1 + index * 3.5}rem`;
    },
  },
  mounted() {
    setTimeout(() => removeWidget(this.data.id), this.data.props.duration_ms || 4000);
  },
});
