<script setup lang="ts">
import { computed } from 'vue'
import { Scatter } from 'vue-chartjs'
import { Chart as ChartJS, LinearScale, PointElement, Tooltip, Legend } from 'chart.js'

ChartJS.register(LinearScale, PointElement, Tooltip, Legend)

const props = defineProps<{ fitted: number[]; residuals: number[] }>()

const chartData = computed(() => ({
  datasets: [{
    label: 'Residuals',
    data: props.fitted.map((f, i) => ({ x: f, y: props.residuals[i] })),
    backgroundColor: 'rgba(59, 130, 246, 0.5)',
  }],
}))

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: (ctx: any) => `Fitted = ${ctx.parsed.x.toFixed(2)}, Residual = ${ctx.parsed.y.toFixed(2)}`,
      },
    },
  },
  scales: {
    x: { title: { display: true, text: 'Fitted values' } },
    y: { title: { display: true, text: 'Residuals' } },
  },
}
</script>

<template>
  <div class="residual-plot">
    <Scatter :data="chartData" :options="chartOptions" />
  </div>
</template>

<style scoped>
.residual-plot { height: 240px; }
</style>
