<script setup lang="ts">
import TopBar from './components/layout/TopBar.vue'
</script>

<template>
  <div class="app-shell">
    <TopBar />
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
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
