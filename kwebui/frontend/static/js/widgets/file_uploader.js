"use strict";

registerWidget("file_uploader", {
  props: ["data"],
  template: `
    <div class="sg-file-uploader">
      <label v-show="data.props.label">{{ data.props.label }}</label>
      <input
        type="file"
        ref="input"
        :accept="data.props.accept || ''"
        :multiple="!!data.props.multiple"
        @change="onChange"
      >
      <span class="sg-file-uploader-status">{{ statusText }}</span>
    </div>
  `,
  data() {
    return { statusText: "" };
  },
  mounted() {
    this.syncStatus();
  },
  updated() {
    this.syncStatus();
  },
  methods: {
    syncStatus() {
      const names = this.data.props.filenames || [];
      if (names.length) {
        this.statusText = `Uploaded: ${names.join(", ")}`;
      }
    },
    async onChange() {
      const input = this.$refs.input;
      if (!input.files.length) return;
      const formData = new FormData();
      for (const file of input.files) formData.append("files", file);
      this.statusText = "Uploading...";
      try {
        const response = await fetch(`/upload/${this.data.id}`, { method: "POST", body: formData });
        const result = await response.json();
        this.statusText = result.ok ? `Uploaded: ${result.filenames.join(", ")}` : (result.error || "Upload failed");
      } catch (err) {
        this.statusText = "Upload failed";
      }
    },
  },
});
