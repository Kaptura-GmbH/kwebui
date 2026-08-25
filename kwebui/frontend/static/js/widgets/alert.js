"use strict";

// One shared component registered under all four alert type names --
// alert.py bakes the level into the widget "type" itself (success/info/
// warning/error), so there's nothing left to branch on here besides CSS.
for (const level of ["success", "info", "warning", "error"]) {
  registerWidget(level, {
    props: ["data"],
    template: `
      <div class="sg-alert sg-alert-${level}">
        <span>{{ data.props.icon || "" }}</span>
        <span>{{ data.props.text }}</span>
      </div>
    `,
  });
}
