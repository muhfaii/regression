<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{ (e: 'file', file: File): void }>()

const dragging = ref(false)
const fileInput = ref<HTMLInputElement>()

function onDrop(event: DragEvent) {
  dragging.value = false
  const file = event.dataTransfer?.files[0]
  if (file) emit('file', file)
}

function onFileInput(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) emit('file', file)
}

function openPicker() {
  fileInput.value?.click()
}
</script>

<template>
  <div
    class="drop-zone"
    :class="{ dragging }"
    role="button"
    tabindex="0"
    aria-label="Upload file — click or drag and drop"
    @dragover.prevent="dragging = true"
    @dragleave="dragging = false"
    @drop.prevent="onDrop"
    @click="openPicker"
    @keydown.enter="openPicker"
    @keydown.space.prevent="openPicker"
  >
    <input
      ref="fileInput"
      type="file"
      accept=".csv,.xlsx,.sav"
      class="sr-only"
      @change="onFileInput"
    />
    <div class="drop-icon" aria-hidden="true">↑</div>
    <p class="drop-primary">Drop your file here, or <span class="link">browse</span></p>
    <p class="drop-hint">Accepts .csv, .xlsx, .sav — up to 100 MB</p>
  </div>
</template>

<style scoped>
.drop-zone {
  border: 2px dashed var(--color-border);
  border-radius: 12px;
  padding: 48px 32px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  user-select: none;
}
.drop-zone:hover,
.drop-zone:focus-visible,
.drop-zone.dragging {
  border-color: var(--color-primary);
  background: #f5f3ff;
  outline: none;
}
.drop-icon {
  font-size: 32px;
  color: var(--color-text-muted);
  margin-bottom: 12px;
}
.drop-primary {
  font-size: 15px;
  font-weight: 500;
  color: var(--color-text);
}
.link {
  color: var(--color-primary);
  text-decoration: underline;
}
.drop-hint {
  font-size: 13px;
  color: var(--color-text-muted);
  margin-top: 4px;
}
</style>
