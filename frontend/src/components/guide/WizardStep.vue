<script setup lang="ts">
defineProps<{
  question: { question: string; options: { value: string | null; label: string; hint?: string }[] }
  step: number
  totalSteps: number
  canGoBack: boolean
}>()

const emit = defineEmits<{
  answer: [value: string | null]
  back: []
}>()
</script>

<template>
  <div class="wizard-wrap">
    <div class="progress-dots" :aria-label="`Step ${step + 1} of ${totalSteps}`">
      <span
        v-for="i in totalSteps"
        :key="i"
        class="dot"
        :class="{ active: i - 1 === step, done: i - 1 < step }"
      />
    </div>

    <div class="wizard-card">
      <p class="step-label">Step {{ step + 1 }} of {{ totalSteps }}</p>
      <h2 class="wizard-question">{{ question.question }}</h2>

      <div class="wizard-options">
        <button
          v-for="opt in question.options"
          :key="String(opt.value)"
          class="wizard-option"
          @click="emit('answer', opt.value)"
        >
          <div class="opt-label">{{ opt.label }}</div>
          <div v-if="opt.hint" class="opt-hint">{{ opt.hint }}</div>
        </button>
      </div>
    </div>

    <button v-if="canGoBack" class="back-btn" @click="emit('back')">← Back</button>
  </div>
</template>

<style scoped>
.wizard-wrap { display: flex; flex-direction: column; gap: 24px; width: 100%; max-width: 560px; margin: 0 auto; }
.progress-dots { display: flex; gap: 8px; justify-content: center; }
.dot { width: 10px; height: 10px; border-radius: 50%; background: var(--color-border); transition: background 0.2s; }
.dot.active { background: var(--color-primary); }
.dot.done { background: var(--color-primary); opacity: 0.4; }
.wizard-card { border: 1px solid var(--color-border); border-radius: 16px; padding: 32px; background: var(--color-bg); }
.step-label { font-size: 12px; color: var(--color-text-muted); margin-bottom: 8px; }
.wizard-question { font-size: 20px; margin-bottom: 24px; }
.wizard-options { display: flex; flex-direction: column; gap: 10px; }
.wizard-option {
  text-align: left; padding: 14px 18px; border: 1px solid var(--color-border);
  border-radius: 10px; background: var(--color-bg); cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.wizard-option:hover { border-color: var(--color-primary); background: #f5f3ff; }
.opt-label { font-size: 14px; font-weight: 500; }
.opt-hint { font-size: 12px; color: var(--color-text-muted); margin-top: 3px; }
.back-btn {
  background: none; border: none; color: var(--color-text-muted); font-size: 13px;
  cursor: pointer; align-self: flex-start; padding: 0;
}
.back-btn:hover { color: var(--color-text); }
</style>
