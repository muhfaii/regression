<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useGuideWizard } from '../composables/useGuideWizard'
import { useAnalysisStore } from '../stores/analysis'
import { getTest } from '../constants/tests'
import WizardStep from '../components/guide/WizardStep.vue'
import RecommendationCard from '../components/guide/RecommendationCard.vue'

const router = useRouter()
const analysis = useAnalysisStore()
const wizard = useGuideWizard()

const recommendedTest = computed(() =>
  wizard.recommendation.value ? getTest(wizard.recommendation.value.test_key) : null
)

function configure() {
  if (!wizard.recommendation.value) return
  analysis.selectTest(wizard.recommendation.value.test_key)
  router.push('/configure')
}
</script>

<template>
  <div class="guide-view">
    <RecommendationCard
      v-if="wizard.showRecommendation.value && wizard.recommendation.value && recommendedTest"
      :test="recommendedTest"
      :reason="wizard.recommendation.value.reason"
      @configure="configure"
      @reset="wizard.reset"
    />
    <WizardStep
      v-else
      :question="wizard.currentQuestion.value"
      :step="wizard.step.value"
      :total-steps="wizard.totalSteps"
      :can-go-back="wizard.step.value > 0"
      @answer="wizard.answer"
      @back="wizard.back"
    />
  </div>
</template>

<style scoped>
.guide-view { display: flex; justify-content: center; padding: 48px 24px; }
</style>
