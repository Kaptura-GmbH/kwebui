"use strict";

registerWidget("workflow_tracker", {
  props: ["data"],
  template: `
    <div class="sg-tracker" :class="'sg-tracker-' + data.props.orientation">
      <template v-for="(task, index) in data.props.tasks" :key="task.id">
        <div class="sg-tracker-step" :class="'sg-tracker-status-' + task.status" @click="select(task)">
          <div class="sg-tracker-circle">
            <span v-if="task.status === 'completed'">✓</span>
            <span v-else-if="task.status === 'error'">✕</span>
            <span v-else>{{ index + 1 }}</span>
          </div>
          <div class="sg-tracker-label">
            <div class="sg-tracker-title">{{ task.title }}</div>
            <div v-if="task.detail" class="sg-tracker-detail">{{ task.detail }}</div>
          </div>
        </div>
        <div
          v-if="index < data.props.tasks.length - 1"
          class="sg-tracker-connector"
          :class="{ 'sg-tracker-connector-filled': task.status === 'completed' || task.status === 'error' }"
        ></div>
      </template>
    </div>
  `,
  methods: {
    select(task) {
      sendEvent(this.data.id, "select", { task_id: task.id });
    },
  },
});
