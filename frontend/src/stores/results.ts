import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { AnalysisResult } from '../types/results'

export const useResultsStore = defineStore('results', () => {
  const history = ref<AnalysisResult[]>([])
  const activeResultId = ref<string | null>(null)

  const hasAnyResult = computed(() => history.value.length > 0)
  const activeResult = computed(() =>
    history.value.find(r => r.result_id === activeResultId.value) ?? null
  )

  function addResult(result: AnalysisResult) {
    history.value.unshift(result)
    activeResultId.value = result.result_id
  }

  function setActive(id: string) {
    activeResultId.value = id
  }

  function clearHistory() {
    history.value = []
    activeResultId.value = null
  }

  return { history, activeResultId, hasAnyResult, activeResult, addResult, setActive, clearHistory }
})
