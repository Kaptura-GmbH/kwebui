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
    // A native <select> always shows some option as selected (the browser
    // defaults to index 0) even when the backend hasn't been told about a
    // selection yet (selected_index is null). Left alone, the first item
    // looks selected in the UI but the backend never finds out -- and if
    // there's only one <option>, the user can never fix this by picking a
    // different item, since a native <select> only fires "change" when the
    // value actually changes. Announce the browser's default once on mount
    // so visual and backend state agree from the start.
    if (
      (this.data.props.selected_index === null || this.data.props.selected_index === undefined) &&
      (this.data.props.items || []).length > 0
    ) {
      this.onChange();
    }
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
