"use strict";

registerWidget("html", {
  props: ["data"],
  template: `<div class="sg-html" v-html="data.props.html || ''"></div>`,
});
