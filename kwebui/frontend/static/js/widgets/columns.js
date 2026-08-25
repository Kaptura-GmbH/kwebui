"use strict";

registerWidget("columns", {
  props: ["data"],
  template: `<div class="sg-columns" :style="{ gap: data.props.gap || '1rem' }"><slot></slot></div>`,
});

registerWidget("column", {
  props: ["data"],
  computed: {
    // No `weight` prop at all (the plain columns(n) form) omits the key
    // entirely, leaving .sg-column's own `flex: 1` class rule in effect
    // -- equal columns render exactly as before this existed. A weight
    // (columns([0.1, 0.2, 0.7])) overrides it with that column's own
    // flex-grow share; flex-basis stays the class rule's 0%, so the row
    // is split strictly by each column's share of the total weight,
    // never by its content's own size.
    flexStyle() {
      const weight = this.data.props.weight;
      return weight != null ? { flex: weight } : {};
    },
  },
  template: `<div class="sg-column" :style="flexStyle"><slot></slot></div>`,
});
