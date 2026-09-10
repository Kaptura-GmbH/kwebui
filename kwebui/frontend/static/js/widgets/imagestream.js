"use strict";

// A 1x1 transparent GIF: pointing the <img> at this is what actually
// tears down the open MJPEG connection (see freeze() below). Used only
// as the fallback for when no frame has been decoded yet and there is
// therefore nothing to snapshot.
const BLANK_PIXEL = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";

// An MJPEG multipart stream is just an image the browser keeps decoding
// frame by frame -- a plain <img> pointed at the stream route is enough,
// no client-side decoding logic needed. The only reactive part is the
// src, and only because of freeze() below.
registerWidget("imagestream", {
  props: ["data"],
  data() {
    return { frozenSrc: null };
  },
  computed: {
    // Same reasoning as image.js's widthStyle -- see there for why this is
    // `width: max-content` rather than `align-self: flex-start`.
    widthStyle() {
      if (this.data.props.stretch) return { width: "100%" };
      const width = this.data.props.width;
      return width > 0 ? { width: `${width}px` } : { width: "max-content" };
    },
    src() {
      return this.frozenSrc || `/stream/${this.data.id}`;
    },
    // Read through a computed rather than referenced directly in the
    // template: Vue only resolves component properties there, not plain
    // module globals like core.js's `state`.
    terminated() {
      return state.terminated;
    },
  },
  watch: {
    terminated(isTerminated) {
      if (isTerminated) this.freeze();
    },
  },
  // A tab can be terminated before this widget ever mounts (it is created
  // fresh from a later "update" message), in which case the watcher never
  // fires -- so check on mount too, or such a widget would open a stream
  // connection the tab is no longer entitled to.
  mounted() {
    document.addEventListener("visibilitychange", this.onVisibilityChange);
    if (state.terminated) this.freeze();
    else this.onVisibilityChange();
  },
  unmounted() {
    document.removeEventListener("visibilitychange", this.onVisibilityChange);
  },
  methods: {
    // A hidden tab is not showing the stream to anyone -- the browser
    // decodes the frames and throws them away -- but it does keep the
    // <img>'s HTTP connection open. That matters far more than the wasted
    // bandwidth: a browser allows only ~6 concurrent HTTP/1.1 connections
    // *per origin*, shared across every tab, and an MJPEG stream never
    // ends. Measured on Chromium: with 6 tabs of a streaming app open, the
    // 7th cannot load the page at all -- its request for "/" queues behind
    // six streams that will never finish, so the app simply hangs. Since
    // tabs pile up on their own (each run of an app tends to open one),
    // this is reachable in ordinary use. Releasing the connection whenever
    // nobody is looking keeps the number of live streams down to the tabs
    // actually on screen.
    onVisibilityChange() {
      if (document.visibilityState === "hidden") this.freeze();
      else this.thaw();
    },
    // Back to live frames. A terminated tab is deliberately excluded: it
    // is dead for good, no matter how often it is looked at.
    thaw() {
      if (state.terminated) return;
      this.frozenSrc = null;
    },
    // Stop pulling frames. The <img> holds its own long-lived HTTP
    // connection to /stream/, completely separate from the WebSocket, so
    // a terminated tab goes on consuming camera frames and one of the
    // browser's few per-origin connection slots until something changes
    // this src. Snapshot the last decoded frame into a data URL first, so
    // what the user is left looking at is the picture that was there --
    // frozen and inert -- rather than a broken-image icon or a hole in
    // the layout.
    freeze() {
      if (this.frozenSrc) return;
      this.frozenSrc = this.snapshot() || BLANK_PIXEL;
    },
    snapshot() {
      const img = this.$el;
      if (!img || !img.naturalWidth) return null;
      try {
        const canvas = document.createElement("canvas");
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        canvas.getContext("2d").drawImage(img, 0, 0);
        // Same-origin stream, so the canvas is never tainted -- but a
        // browser that refuses this anyway must still end up dropping the
        // connection, hence the BLANK_PIXEL fallback in freeze().
        return canvas.toDataURL("image/jpeg", 0.85);
      } catch (err) {
        return null;
      }
    },
  },
  template: `<img class="sg-imagestream" :src="src" :style="widthStyle">`,
});
