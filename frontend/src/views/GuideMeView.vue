<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { WIZARD_QUESTIONS, resolveTest, type WizardAnswers } from '../constants/wizard'
import { useAnalysisStore } from '../stores/analysis'
import { getTest } from '../constants/tests'

const router = useRouter()
const analysis = useAnalysisStore()

const answers = ref<(string | null)[]>([null, null, null, null])
const step = ref(0)
const direction = ref<'forward' | 'back'>('forward')
const showRecommendation = ref(false)
const recommendation = ref<{ test_key: string; reason: string } | null>(null)

const currentQuestion = computed(() => WIZARD_QUESTIONS[step.value])
const totalSteps = WIZARD_QUESTIONS.length

function answer(value: string | null) {
  answers.value[step.value] = value
  direction.value = 'forward'

  if (step.value < totalSteps - 1) {
    if (step.value === 0 && value !== 'compare') {
      answers.value[1] = null
      step.value = 2
    } else {
      step.value++
    }
  } else {
    // Last question answered — resolve recommendation
    const result = resolveTest(answers.value as WizardAnswers)
    recommendation.value = result
    showRecommendation.value = true
  }
}

function back() {
  if (step.value > 0) {
    direction.value = 'back'
    showRecommendation.value = false
    if (step.value === 2 && answers.value[0] !== 'compare') {
      step.value = 0
    } else {
      step.value--
    }
  }
}

function startOver() {
  answers.value = [null, null, null, null]
  step.value = 0
  showRecommendation.value = false
  recommendation.value = null
}

function configure() {
  if (!recommendation.value) return
  analysis.selectTest(recommendation.value.test_key)
  router.push('/configure')
}

const recommendedTest = computed(() =>
  recommendation.value ? getTest(recommendation.value.test_key) : null
)
</script>

<template>
  <div class="guide-view">
    <!-- Recommendation screen -->
    <div v-if="showRecommendation && recommendation && recommendedTest" class="recommendation-card" role="status" aria-live="polite">
      <div class="rec-tag">Recommended test</div>
      <h2 class="rec-test-name">{{ recommendedTest.name }}</h2>
      <p class="rec-reason">{{ recommendation.reason }}</p>

      <div class="rec-assumptions">
        <div class="rec-section-label">Assumption checks that will run:</div>
        <p class="rec-assumption-note">Normality, equal variances, and other relevant checks will run automatically — no setup needed.</p>
      </div>

      <div class="rec-actions">
        <button class="btn-primary" @click="configure">Configure &amp; run →</button>
        <button class="btn-ghost" @click="startOver">Start over</button>
      </div>
    </div>

    <!-- Wizard steps -->
    <div v-else class="wizard">
      <!-- Progress dots -->
      <div class="progress-dots" :aria-label="`Step ${step + 1} of ${totalSteps}`">
        <span
          v-for="i in totalSteps"
          :key="i"
          class="dot"
          :class="{ active: i - 1 === step, done: i - 1 < step }"
        />
      </div>

      <Transition :name="direction === 'forward' ? 'slide-fwd' : 'slide-back'" mode="out-in">
        <div class="wizard-card" :key="step">
          <p class="step-label">Step {{ step + 1 }} of {{ totalSteps }}</p>
          <h2 class="wizard-question">{{ currentQuestion.question }}</h2>

          <div class="wizard-options">
            <button
              v-for="opt in currentQuestion.options"
              :key="String(opt.value)"
              class="wizard-option"
              @click="answer(opt.value)"
            >
              <div class="opt-label">{{ opt.label }}</div>
              <div v-if="'hint' in opt && opt.hint" class="opt-hint">{{ opt.hint }}</div>
            </button>
          </div>
        </div>
      </Transition>

      <button v-if="step > 0" class="back-btn" @click="back">← Back</button>
    </div>
  </div>
</template>

<style scoped>
.guide-view {
  display: flex;
  justify-content: center;
  padding: 48px 24px;
}
.wizard, .recommendation-card {
  width: 100%;
  max-width: 560px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.progress-dots {
  display: flex;
  gap: 8px;
  justify-content: center;
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--color-border);
  transition: background 0.2s;
}
.dot.active { background: var(--color-primary); }
.dot.done { background: var(--color-primary); opacity: 0.4; }
.slide-fwd-enter-active,
.slide-fwd-leave-active,
.slide-back-enter-active,
.slide-back-leave-active { transition: transform 0.2s ease, opacity 0.15s ease; }
.slide-fwd-enter-from { transform: translateX(24px); opacity: 0; }
.slide-fwd-leave-to   { transform: translateX(-24px); opacity: 0; }
.slide-back-enter-from { transform: translateX(-24px); opacity: 0; }
.slide-back-leave-to   { transform: translateX(24px); opacity: 0; }

.wizard-card {
  border: 1px solid var(--color-border);
  border-radius: 16px;
  padding: 32px;
  background: var(--color-bg);
}
.step-label { font-size: 12px; color: var(--color-text-muted); margin-bottom: 8px; }
.wizard-question { font-size: 20px; margin-bottom: 24px; }
.wizard-options { display: flex; flex-direction: column; gap: 10px; }
.wizard-option {
  text-align: left;
  padding: 14px 18px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-bg);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.wizard-option:hover { border-color: var(--color-primary); background: #f5f3ff; }
.opt-label { font-size: 14px; font-weight: 500; }
.opt-hint { font-size: 12px; color: var(--color-text-muted); margin-top: 3px; }
.back-btn {
  background: none;
  border: none;
  color: var(--color-text-muted);
  font-size: 13px;
  cursor: pointer;
  align-self: flex-start;
  padding: 0;
}
.back-btn:hover { color: var(--color-text); }

/* Recommendation */
.recommendation-card {
  border: 1px solid var(--color-border);
  border-radius: 16px;
  padding: 36px;
}
.rec-tag {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--color-primary);
  margin-bottom: 8px;
}
.rec-test-name { font-size: 24px; margin-bottom: 12px; }
.rec-reason { font-size: 14px; color: var(--color-text-muted); line-height: 1.6; }
.rec-assumptions {
  background: var(--color-surface);
  border-radius: 8px;
  padding: 14px 16px;
}
.rec-section-label { font-size: 12px; font-weight: 700; color: var(--color-text-muted); margin-bottom: 6px; }
.rec-assumption-note { font-size: 13px; color: var(--color-text-muted); }
.rec-actions { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.btn-primary {
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 11px 22px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-ghost {
  background: none;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 10px 16px;
  font-size: 14px;
  color: var(--color-text-muted);
  cursor: pointer;
}
.btn-ghost:hover { border-color: var(--color-text-muted); color: var(--color-text); }
</style>
