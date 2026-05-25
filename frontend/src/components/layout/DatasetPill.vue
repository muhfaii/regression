<script setup lang="ts">
defineProps<{ filename: string | null }>()
</script>

<template>
  <div class="pill" :class="{ loaded: !!filename }">
    <span v-if="filename" class="check" aria-hidden="true">✓</span>
    <span role="status">{{ filename ?? 'No data loaded' }}</span>
  </div>
</template>

<style scoped>
.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 99px;
  font-size: 13px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  color: var(--color-text-muted);
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pill.loaded {
  color: var(--color-text);
}
.check {
  color: var(--color-green);
  font-size: 12px;
  flex-shrink: 0;
}
</style>
