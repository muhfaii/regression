<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const STEPS = ['Import data', 'Choose analysis', 'Configure', 'Results']

const currentStep = computed(() => route.meta?.step as number | undefined)
</script>

<template>
  <div v-if="currentStep" class="workflow-steps" :aria-label="`Step ${currentStep} of ${STEPS.length}: ${STEPS[currentStep - 1]}`">
    <div
      v-for="(label, i) in STEPS"
      :key="label"
      class="step"
      :class="{ done: i + 1 < currentStep, active: i + 1 === currentStep }"
    >
      <span class="step-index">{{ i + 1 }}</span>
      <span class="step-label">{{ label }}</span>
      <span v-if="i < STEPS.length - 1" class="step-sep" aria-hidden="true">→</span>
    </div>
  </div>
</template>

<style scoped>
.workflow-steps {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 24px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
  font-size: 12px;
  overflow-x: auto;
}
.step {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--color-text-muted);
  white-space: nowrap;
}
.step-index {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 1px solid var(--color-border);
  font-weight: 600;
  font-size: 11px;
  flex-shrink: 0;
}
.step.done .step-index {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}
.step.active .step-index {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.step.active .step-label {
  color: var(--color-text);
  font-weight: 600;
}
.step-sep {
  color: var(--color-border);
  margin-left: 8px;
}
</style>
