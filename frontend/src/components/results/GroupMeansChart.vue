<script setup lang="ts">
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip, Legend } from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)

const props = defineProps<{ groups: Record<string, { n: number; mean: number; sd: number }> }>()

const labels = computed(() => Object.keys(props.groups))

const chartData = computed(() => ({
  labels: labels.value,
  datasets: [{
    label: 'Mean ± 1 SD',
    data: labels.value.map((g): [number, number] => {
      const s = props.groups[g]
      return [Number((s.mean - s.sd).toFixed(4)), Number((s.mean + s.sd).toFixed(4))]
    }),
    backgroundColor: 'rgba(124, 58, 237, 0.35)',
    borderColor: 'rgba(124, 58, 237, 0.9)',
    borderWidth: 1,
  }],
}))

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: (ctx: any) => {
          const g = props.groups[ctx.label]
          return `Mean = ${g.mean.toFixed(2)}, SD = ${g.sd.toFixed(2)}, n = ${g.n}`
        },
      },
    },
  },
  scales: {
    y: { title: { display: true, text: 'Value' } },
  },
}))
</script>

<template>
  <div class="group-means-chart">
    <Bar :data="chartData" :options="chartOptions" />
  </div>
</template>

<style scoped>
.group-means-chart { height: 220px; }
</style>
