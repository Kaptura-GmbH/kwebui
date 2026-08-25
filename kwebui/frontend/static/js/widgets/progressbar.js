"use strict";

registerWidget("progressbar", {
  props: ["data"],
  template: `
    <div class="sg-progress" :class="{ 'sg-indeterminate': !!data.props.indeterminate }">
      <div class="sg-progress-bar" :style="{ width: data.props.value + '%' }"></div>
    </div>
  `,
});
