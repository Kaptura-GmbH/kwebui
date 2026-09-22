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
    // A column takes container's layout options too (see columns.py's
    // ColumnPlugin). These are applied straight to .sg-column, which is
    // already `display: flex; flex-direction: column` (base.css) -- so
    // every one of them omits its key when unset, and a column with no
    // options set renders byte-identically to before they existed.
    // Same axis-swap reasoning as container.js's alignStyle.
    layoutStyle() {
      const props = this.data.props;
      const style = {};
      if (props.direction === "horizontal") style.flexDirection = "row";
      if (props.wrap) style.flexWrap = "wrap";
      if (props.height > 0) style.height = `${props.height}px`;

      const h = { left: "flex-start", center: "center", right: "flex-end" }[props.horizontal_alignment];
      const v = { top: "flex-start", center: "center", bottom: "flex-end" }[props.vertical_alignment];
      const horizontal = props.direction === "horizontal";
      if (h) style[horizontal ? "justifyContent" : "alignItems"] = h;
      if (v) style[horizontal ? "alignItems" : "justifyContent"] = v;

      // Unlike container's body, a column has no padding of its own by
      // default, so an unset padding means exactly none -- there is no
      // theme variable to defer to here.
      const vp = props.vertical_padding;
      const hp = props.horizontal_padding;
      if (vp != null || hp != null) style.padding = `${vp == null ? 0 : vp}px ${hp == null ? 0 : hp}px`;
      return style;
    },
    // Only worth a <fieldset> when there is actually a border or caption
    // to draw. Without this a plain column would gain a wrapper element
    // (and the browser's default fieldset box) for nothing.
    framed() {
      return Boolean(this.data.props.border) || Boolean(this.data.props.caption);
    },
  },
  // Two shapes on purpose: the bare div is the historical rendering and
  // stays the default; the framed one reuses .sg-container/.sg-container-
  // caption so a bordered column looks exactly like a bordered container,
  // with no new CSS.
  template: `
    <div class="sg-column" :style="[flexStyle, framed ? {} : layoutStyle]">
      <fieldset
        v-if="framed"
        class="sg-container sg-column-frame"
        :data-border="!!data.props.border"
        :data-rounded="!!data.props.border_roundness"
      >
        <legend v-if="data.props.caption" class="sg-container-caption">{{ data.props.caption }}</legend>
        <div class="sg-container-body" :style="layoutStyle"><slot></slot></div>
      </fieldset>
      <slot v-else></slot>
    </div>
  `,
});
