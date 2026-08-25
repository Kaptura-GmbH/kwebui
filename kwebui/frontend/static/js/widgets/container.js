"use strict";

registerWidget("container", {
  props: ["data"],
  computed: {
    // Mirrors image.js's widthStyle -- see there for why this is
    // `width: max-content` rather than `align-self: flex-start` (it's
    // what lets a *parent* container's `horizontal_alignment` reposition
    // a nested, unstretched container instead of that nested container's
    // own alignSelf overriding it).
    widthStyle() {
      if (this.data.props.stretch) return { width: "100%" };
      const width = this.data.props.width;
      return width > 0 ? { width: `${width}px` } : { width: "max-content" };
    },
    // No stretch-equivalent or ambient-default to escape here, unlike
    // widthStyle: a flex column's main axis (height) is never stretched
    // by an ambient parent default the way the cross axis (width) is, so
    // -1/0 (the default) simply omits the style key and the container
    // sizes to its content, no `height: max-content` workaround needed.
    heightStyle() {
      const height = this.data.props.height;
      return height > 0 ? { height: `${height}px` } : {};
    },
    // This container's own align-items/justify-content, positioning ITS
    // children -- unrelated to widthStyle above, which is about how THIS
    // container itself is sized/positioned within its own parent. Maps
    // the user-facing left/right/top/bottom words to their flexbox
    // equivalents; left/right isn't valid CSS for align-items (only
    // flex-start/flex-end are). Omitting the key entirely (rather than
    // mapping a null/unset alignment to "stretch"/"flex-start" explicitly)
    // is what keeps the default byte-identical to before this prop
    // existed -- see create()'s docstring in container.py for why that
    // matters (alert/listbox/textedit/slider all lean on the inherited
    // default).
    alignStyle() {
      const style = {};
      const h = { left: "flex-start", center: "center", right: "flex-end" }[this.data.props.horizontal_alignment];
      if (h) style.alignItems = h;
      const v = { top: "flex-start", center: "center", bottom: "flex-end" }[this.data.props.vertical_alignment];
      if (v) style.justifyContent = v;
      return style;
    },
    // null/undefined (the default -- Python's None) means "use the
    // theme's own default", so it omits the key entirely and lets
    // .sg-container-body's own CSS rule (padding: var(--sg-container-
    // padding-vertical) var(--sg-container-padding-horizontal), see
    // base.css) apply -- an inline style here always wins over that rule
    // regardless of specificity, which is exactly what makes an explicit
    // vertical_padding/horizontal_padding "overwrite the theme". 0 is a
    // real, distinct value from null: it's an explicit "no padding"
    // override, not "defer to the theme". Each axis is independent, so
    // e.g. only vertical_padding set still lets horizontal fall through
    // to its own theme variable in the same inline shorthand.
    paddingStyle() {
      const v = this.data.props.vertical_padding;
      const h = this.data.props.horizontal_padding;
      if (v == null && h == null) return {};
      const vv = v == null ? "var(--sg-container-padding-vertical)" : `${v}px`;
      const hh = h == null ? "var(--sg-container-padding-horizontal)" : `${h}px`;
      return { padding: `${vv} ${hh}` };
    },
  },
  // heightStyle/alignStyle apply to the inner .sg-container-body div, not
  // this fieldset -- see base.css's comment on .sg-container for why: a
  // <fieldset display:flex> whose own parent is also flex (always true
  // here) silently breaks justify-content, so the fieldset stays a plain
  // non-flex box (border/legend/width only) and the actual flex-column
  // layout for children lives one level down, on a div whose parent
  // (this fieldset) is never itself flex.
  template: `
    <fieldset
      class="sg-container"
      :style="widthStyle"
      :data-border="!!data.props.border"
      :data-rounded="!!data.props.border_roundness"
    >
      <legend v-if="data.props.caption" class="sg-container-caption">{{ data.props.caption }}</legend>
      <div class="sg-container-body" :style="[heightStyle, alignStyle, paddingStyle]">
        <slot></slot>
      </div>
    </fieldset>
  `,
});
