<script setup lang="ts">
import TopBar from './components/layout/TopBar.vue'
</script>

<template>
  <div class="app-shell">
    <TopBar />
    <main class="app-main">
      <Transition name="fade" mode="out-in">
        <RouterView />
      </Transition>
    </main>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from,
.fade-leave-to { opacity: 0; }

.app-shell {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}
.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
}
</style>
