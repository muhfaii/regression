import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { AnalysisConfig } from '../types/analysis'
import { getTest } from '../constants/tests'

export const useAnalysisStore = defineStore('analysis', () => {
  const selectedTestKey = ref<string | null>(null)
  const config = ref<AnalysisConfig>({})
  const isRunning = ref(false)
  const validationErrors = ref<string[]>([])
  const options = ref({
    assumption_checks: true,
    effect_size: true,
    post_hoc: false,
    se_type: 'auto',
    p_adjust: 'none',
  })

  const selectedTest = computed(() => selectedTestKey.value ? getTest(selectedTestKey.value) : null)

  const requiredSlotsFilled = computed(() => {
    if (!selectedTest.value) return false
    return selectedTest.value.slots
      .filter(s => !s.multiple)
      .every(s => {
        const val = config.value[s.key]
        return val && (Array.isArray(val) ? val.length > 0 : val !== '')
      })
  })

  function selectTest(key: string) {
    selectedTestKey.value = key
    config.value = {}
    validationErrors.value = []
  }

  function updateConfig(partial: Record<string, string | string[]>) {
    config.value = { ...config.value, ...partial }
  }

  function setRunning(running: boolean) {
    isRunning.value = running
  }

  function clearConfig() {
    selectedTestKey.value = null
    config.value = {}
    isRunning.value = false
    validationErrors.value = []
  }

  return {
    selectedTestKey, config, isRunning, validationErrors, options,
    selectedTest, requiredSlotsFilled,
    selectTest, updateConfig, setRunning, clearConfig,
  }
})
