<script setup lang="ts">
import { computed } from 'vue'
import { useAnalysisStore } from '../stores/analysis'
import { TEST_CATALOG, TEST_CATEGORIES } from '../constants/tests'

const analysis = useAnalysisStore()

const grouped = computed(() =>
  TEST_CATEGORIES.map(cat => ({
    category: cat,
    tests: TEST_CATALOG.filter(t => t.category === cat),
  }))
)

function select(key: string) {
  const test = TEST_CATALOG.find(t => t.key === key)
  if (test?.coming_soon) return
  analysis.selectTest(key)
}
</script>

<template>
  <div class="browse-view">
    <!-- Sidebar -->
    <aside class="test-sidebar">
      <div class="sidebar-pinned">
        <a href="/guide" class="not-sure-link">Not sure which test? →</a>
      </div>

      <nav>
        <div v-for="group in grouped" :key="group.category" class="sidebar-group">
          <div class="sidebar-category">{{ group.category }}</div>
          <button
            v-for="test in group.tests"
            :key="test.key"
            class="sidebar-item"
            :class="{
              active: analysis.selectedTestKey === test.key,
              'coming-soon': test.coming_soon,
            }"
            :data-tooltip="test.coming_soon ? 'This test is coming soon.' : test.tooltip"
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
      <div v-if="!analysis.selectedTestKey" class="empty-state">
        <div class="empty-icon">⬡</div>
        <p class="empty-primary">Select a test from the sidebar to get started</p>
        <p class="empty-secondary">Select a test from the sidebar to configure variables and run the analysis.</p>
      </div>
      <RouterView v-else />
    </div>
  </div>
</template>

<style scoped>
.browse-view {
  display: flex;
  flex: 1;
  height: calc(100vh - var(--topbar-h));
  overflow: hidden;
}
.test-sidebar {
  width: var(--sidebar-w);
  flex-shrink: 0;
  border-right: 1px solid var(--color-border);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}
.sidebar-pinned {
  position: sticky;
  top: 0;
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
  padding: 10px 12px;
  z-index: 10;
}
.not-sure-link {
  display: block;
  text-align: center;
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  background: var(--color-primary);
  padding: 8px 12px;
  border-radius: 20px;
  text-decoration: none;
  transition: background 0.15s;
}
.not-sure-link:hover { background: var(--color-primary-hover); }
.sidebar-group { padding: 8px 0; }
.sidebar-category {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-muted);
  padding: 6px 14px 4px;
}
.sidebar-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  text-align: left;
  padding: 7px 14px;
  background: none;
  border: none;
  font-size: 13px;
  color: var(--color-text);
  cursor: pointer;
  border-radius: 0;
  gap: 6px;
  transition: background 0.1s;
  position: relative;
}
.sidebar-item:hover:not(:disabled) { background: var(--color-surface); }
.sidebar-item.active { background: #ede9fe; color: var(--color-primary); font-weight: 600; }
.sidebar-item.coming-soon { opacity: 0.5; cursor: default; }
.item-name { flex: 1; }
.item-desc { font-size: 11px; color: var(--color-text-muted); white-space: nowrap; }
/* Hover tooltip for all sidebar items */
.sidebar-item[data-tooltip]:hover::after {
  content: attr(data-tooltip);
  position: absolute;
  left: calc(100% + 10px);
  top: 50%;
  transform: translateY(-50%);
  background: #1e1e2e;
  color: #fff;
  font-size: 12px;
  font-weight: 400;
  line-height: 1.45;
  padding: 7px 11px;
  border-radius: 7px;
  max-width: 220px;
  white-space: normal;
  z-index: 200;
  pointer-events: none;
  box-shadow: 0 4px 12px rgba(0,0,0,0.18);
}
.sidebar-item[data-tooltip]:hover::before {
  content: '';
  position: absolute;
  left: 100%;
  top: 50%;
  transform: translateY(-50%);
  border: 5px solid transparent;
  border-right-color: #1e1e2e;
  z-index: 200;
  pointer-events: none;
}
.badge-soon {
  font-size: 10px;
  font-weight: 700;
  color: var(--color-text-muted);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 99px;
  padding: 1px 6px;
}
.browse-main {
  flex: 1;
  overflow-y: auto;
  padding: 32px;
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 10px;
  border: 1px dashed var(--color-border);
  border-radius: 16px;
  padding: 48px 32px;
  text-align: center;
}
.empty-icon { font-size: 36px; color: var(--color-border); line-height: 1; }
.empty-primary { font-size: 16px; font-weight: 600; color: var(--color-text); margin: 0; }
.empty-secondary { font-size: 13px; color: var(--color-text-muted); margin: 0; max-width: 280px; line-height: 1.5; }
</style>
