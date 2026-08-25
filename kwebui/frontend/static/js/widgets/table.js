"use strict";

registerWidget("table", {
  props: ["data"],
  computed: {
    // Mirrors image.js's widthStyle -- see there for why this is
    // `width: max-content` rather than `align-self: flex-start`.
    widthStyle() {
      if (this.data.props.stretch) return { width: "100%" };
      const width = this.data.props.width;
      return width > 0 ? { width: `${width}px` } : { width: "max-content" };
    },
  },
  template: `
    <table class="sg-table" :style="widthStyle" :data-border="!!data.props.border">
      <thead v-if="!data.props.hide_header">
        <tr>
          <th v-for="(col, i) in data.props.columns" :key="i">{{ col }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, ri) in data.props.rows" :key="ri">
          <td v-for="(cell, ci) in row" :key="ci">{{ cell }}</td>
        </tr>
      </tbody>
    </table>
  `,
});
