"use strict";

registerWidget("json", {
  props: ["data"],
  template: `<pre class="sg-json">{{ JSON.stringify(data.props.data, null, 2) }}</pre>`,
});
