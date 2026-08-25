// Bootstrap: mount the Vue app, then open the WebSocket connection.
// Mounting doesn't wait on the connection -- it renders an empty page
// (state.widgets starts as []) until "init" arrives and populates it.
"use strict";

document.addEventListener("DOMContentLoaded", () => {
  vueApp.mount("#app-root");
  connect();
});
