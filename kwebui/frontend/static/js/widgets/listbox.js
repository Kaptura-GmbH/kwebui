"use strict";

registerWidget("listbox", {
  props: ["data"],
  template: `
    <select class="sg-listbox" ref="select" @change="onChange">
      <option v-for="(item, index) in data.props.items || []" :key="index">{{ item }}</option>
    </select>
  `,
  mounted() {
    this.syncSelection();
  },
  updated() {
    this.syncSelection();
  },
  methods: {
    onChange() {
      sendEvent(this.data.id, "select", { index: this.$refs.select.selectedIndex });
    },
    syncSelection() {
      const index = this.data.props.selected_index;
      if (index !== null && index !== undefined) {
        this.$refs.select.selectedIndex = index;
      }
    },
  },
});
