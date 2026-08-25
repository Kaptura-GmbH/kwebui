"use strict";

// An MJPEG multipart stream is just an image the browser keeps decoding
// frame by frame -- a plain <img> pointed at the stream route is enough,
// no client-side decoding logic needed. No props ever change after
// mount, so there's nothing reactive to bind beyond the id-derived src.
registerWidget("imagestream", {
  props: ["data"],
  computed: {
    // Same reasoning as image.js's widthStyle -- see there for why this is
    // `width: max-content` rather than `align-self: flex-start`.
    widthStyle() {
      if (this.data.props.stretch) return { width: "100%" };
      const width = this.data.props.width;
      return width > 0 ? { width: `${width}px` } : { width: "max-content" };
    },
  },
  template: `<img class="sg-imagestream" :src="'/stream/' + data.id" :style="widthStyle">`,
});
