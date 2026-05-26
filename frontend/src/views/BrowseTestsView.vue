<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAnalysisStore } from '../stores/analysis'
import { TEST_CATALOG, TEST_CATEGORIES, getTest } from '../constants/tests'
import { useGuideWizard } from '../composables/useGuideWizard'
import WizardStep from '../components/guide/WizardStep.vue'
import RecommendationCard from '../components/guide/RecommendationCard.vue'

const router = useRouter()
const analysis = useAnalysisStore()
const showWizard = ref(false)
const wizard = useGuideWizard()

const grouped = computed(() =>
  TEST_CATEGORIES.map(cat => ({
    category: cat,
    tests: TEST_CATALOG.filter(t => t.category === cat),
  }))
)

const recommendedTest = computed(() =>
  wizard.recommendation.value ? getTest(wizard.recommendation.value.test_key) : null
)

function select(key: string) {
  const test = TEST_CATALOG.find(t => t.key === key)
  if (test?.coming_soon) return
  showWizard.value = false
  analysis.selectTest(key)
}

function openWizard() {
  wizard.reset()
  showWizard.value = true
}

function configureFromWizard() {
  if (!wizard.recommendation.value) return
  analysis.selectTest(wizard.recommendation.value.test_key)
  showWizard.value = false
  router.push('/configure')
}
</script>

<template>
  <div class="browse-view">
    <!-- Sidebar -->
    <aside class="test-sidebar">
      <div class="sidebar-pinned">
        <button class="not-sure-btn" @click="openWizard">Not sure which test? →</button>
      </div>

      <nav>
        <div v-for="group in grouped" :key="group.category" class="sidebar-group">
          <div class="sidebar-category">{{ group.category }}</div>
          <button
            v-for="test in group.tests"
            :key="test.key"
            class="sidebar-item"
            :class="{
              active: analysis.selectedTestKey === test.key && !showWizard,
              'coming-soon': test.coming_soon,
            }"
            :data-tooltip="test.tooltip"
            :disabled="test.coming_soon"
            @click="select(test.key)"
          >
            <span class="item-name">{{ test.name }}</span>
            <span v-if="test.coming_soon" class="badge-soon">Soon</span>
            <span v-else class="item-desc">{{ test.descriptor }}</span>
          </button>
        </div>
      </nav>
    </aside>

    <!-- Main content area -->
    <div class="browse-main">
      <!-- Inline wizard -->
      <template v-if="showWizard">
        <RecommendationCard
          v-if="wizard.showRecommendation.value && wizard.recommendation.value && recommendedTest"
          :test="recommendedTest"
          :reason="wizard.recommendation.value.reason"
          configure-label="Select this test →"
          @configure="configureFromWizard"
          @reset="wizard.reset"
        />
        <WizardStep
          v-else
          :question="wizard.currentQuestion.value"
          :step="wizard.step.value"
          :total-steps="wizard.totalSteps"
          :can-go-back="wizard.step.value > 0 || wizard.showRecommendation.value"
          @answer="wizard.answer"
          @back="wizard.back"
        />
      </template>

      <div v-else-if="!analysis.selectedTestKey" class="empty-state">
        <p>Select a test from the sidebar to configure and run it.</p>
      </div>
      <RouterView v-else />
    </div>
  </div>
</template>

<style scoped>
.browse-view { display: flex; flex: 1; height: calc(100vh - var(--topbar-h)); overflow: hidden; }
.test-sidebar {
  width: var(--sidebar-w); flex-shrink: 0; border-right: 1px solid var(--color-border);
  overflow-y: auto; display: flex; flex-direction: column;
}
.sidebar-pinned {
  position: sticky; top: 0; background: var(--color-bg);
  border-bottom: 1px solid var(--color-border); padding: 10px 12px; z-index: 10;
}
.not-sure-btn {
  background: none; border: none; padding: 0; font-size: 12px; font-weight: 600;
  color: var(--color-primary); cursor: pointer; text-align: left;
}
.not-sure-btn:hover { text-decoration: underline; }
.sidebar-group { padding: 8px 0; }
.sidebar-category {
  font-size: 11px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--color-text-muted); padding: 6px 14px 4px;
}
.sidebar-item {
  display: flex; align-items: center; justify-content: space-between; width: 100%;
  text-align: left; padding: 7px 14px; background: none; border: none;
  font-size: 13px; color: var(--color-text); cursor: pointer; border-radius: 0;
  gap: 6px; transition: background 0.1s; position: relative;
}
.sidebar-item:hover:not(:disabled) { background: var(--color-surface); }
.sidebar-item.active { background: #ede9fe; color: var(--color-primary); font-weight: 600; }
.sidebar-item.coming-soon { opacity: 0.5; cursor: default; }
.item-name { flex: 1; }
.item-desc { font-size: 11px; color: var(--color-text-muted); white-space: nowrap; }
.badge-soon {
  font-size: 10px; font-weight: 700; color: var(--color-text-muted);
  background: var(--color-surface); border: 1px solid var(--color-border);
  border-radius: 99px; padding: 1px 6px;
}
.browse-main { flex: 1; overflow-y: auto; padding: 32px; }
.empty-state {
  display: flex; align-items: center; justify-content: center;
  height: 100%; color: var(--color-text-muted); font-size: 14px;
}
</style>
