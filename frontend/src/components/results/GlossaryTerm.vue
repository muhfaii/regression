<script setup lang="ts">
import { computed } from 'vue'
import { GLOSSARY } from '../../constants/glossary'

const props = defineProps<{ term: string; label?: string }>()
const definition = computed(() => GLOSSARY[props.term])
const displayLabel = computed(() => props.label ?? props.term)
</script>

<template>
  <span v-if="definition" class="glossary-term" tabindex="0" role="button" :aria-label="`${displayLabel}: ${definition}`">
    {{ displayLabel }}
    <span class="glossary-tooltip" role="tooltip">{{ definition }}</span>
  </span>
  <span v-else>{{ displayLabel }}</span>
</template>

<style scoped>
.glossary-term {
  position: relative;
  border-bottom: 1px dotted var(--color-text-muted);
  cursor: help;
}
.glossary-tooltip {
  position: absolute;
  bottom: 130%;
  left: 50%;
  transform: translateX(-50%);
  background: #1f2937;
  color: #fff;
  font-size: 11px;
  font-weight: 400;
  padding: 7px 10px;
  border-radius: 6px;
  width: max-content;
  max-width: 220px;
  white-space: normal;
  line-height: 1.4;
  text-align: left;
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition: opacity 0.12s;
  z-index: 30;
}
.glossary-term:hover .glossary-tooltip,
.glossary-term:focus .glossary-tooltip,
.glossary-term:focus-within .glossary-tooltip {
  opacity: 1;
  visibility: visible;
}
</style>
