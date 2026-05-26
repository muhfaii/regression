import { ref, computed } from 'vue'
import { WIZARD_QUESTIONS, resolveTest, type WizardAnswers } from '../constants/wizard'

export function useGuideWizard() {
  const answers = ref<(string | null)[]>([null, null, null, null])
  const step = ref(0)
  const showRecommendation = ref(false)
  const recommendation = ref<{ test_key: string; reason: string } | null>(null)

  const currentQuestion = computed(() => WIZARD_QUESTIONS[step.value])
  const totalSteps = WIZARD_QUESTIONS.length

  function answer(value: string | null) {
    answers.value[step.value] = value
    if (step.value < totalSteps - 1) {
      if (step.value === 0 && value !== 'compare') {
        answers.value[1] = null
        step.value = 2
      } else {
        step.value++
      }
    } else {
      recommendation.value = resolveTest(answers.value as WizardAnswers)
      showRecommendation.value = true
    }
  }

  function back() {
    if (showRecommendation.value) {
      showRecommendation.value = false
      return
    }
    if (step.value > 0) {
      if (step.value === 2 && answers.value[0] !== 'compare') {
        step.value = 0
      } else {
        step.value--
      }
    }
  }

  function reset() {
    answers.value = [null, null, null, null]
    step.value = 0
    showRecommendation.value = false
    recommendation.value = null
  }

  return {
    answers,
    step,
    totalSteps,
    currentQuestion,
    showRecommendation,
    recommendation,
    answer,
    back,
    reset,
  }
}
