"use strict";

registerWidget("image", {
  props: ["data"],
  computed: {
    // stretch=true wins outright (fills the parent's width, ignoring
    // `width`). Otherwise width <= 0 (the default) means "use the image's
    // own size" -- given via an explicit `width: max-content` rather than
    // `align-self: flex-start`, specifically so a flex parent's
    // `align-items` (e.g. container's `horizontal_alignment`) can still
    // position the now content-sized image; `align-self` would have
    // overridden that positioning outright instead of deferring to it.
    // Without this, the flex parent's default align-items: stretch would
    // otherwise stretch the box to the container's full width regardless
    // of the image's intrinsic size.
    widthStyle() {
      if (this.data.props.stretch) return { width: "100%" };
      const width = this.data.props.width;
      return width > 0 ? { width: `${width}px` } : { width: "max-content" };
    },
  },
  template: `<img class="sg-image" :src="data.props.src" :style="widthStyle">`,
});
