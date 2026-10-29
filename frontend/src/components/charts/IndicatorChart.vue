<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted } from 'vue';
import * as echarts from 'echarts';
import type { IndicatorDistributionResponse } from '../../types/history';

interface Props {
  data: IndicatorDistributionResponse | null;
  metricType: 'sum' | 'ac' | 'oddEven' | 'span';
}

const props = withDefaults(defineProps<Props>(), {
  data: null,
  metricType: 'sum',
});

const chartRef = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

function renderChart() {
  if (!chartRef.value || !props.data) return;

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value, 'dark');
  }

  let categories: string[] = [];
  let seriesData: number[] = [];
  let title = '';
  let barColor = '#00d2d3';

  if (props.metricType === 'sum') {
    title = '和值分布 (80% 常见区间 75-135)';
    categories = Object.keys(props.data.sum_distribution);
    seriesData = Object.values(props.data.sum_distribution);
    barColor = '#3b82f6';
  } else if (props.metricType === 'ac') {
    title = 'AC值分布 (复杂度和，通常 ≥ 6)';
    categories = Object.keys(props.data.ac_distribution).map((k) => `AC=${k}`);
    seriesData = Object.values(props.data.ac_distribution);
    barColor = '#10b981';
  } else if (props.metricType === 'oddEven') {
    title = '奇偶比分布 (奇:偶)';
    categories = Object.keys(props.data.odd_even_distribution);
    seriesData = Object.values(props.data.odd_even_distribution);
    barColor = '#ff4757';
  } else if (props.metricType === 'span') {
    title = '跨度分布 (首尾红球差)';
    categories = Object.keys(props.data.span_distribution);
    seriesData = Object.values(props.data.span_distribution);
    barColor = '#f59e0b';
  }

  const option: echarts.EChartsOption = {
    backgroundColor: '#111827',
    title: {
      text: title,
      textStyle: { color: '#f8fafc', fontSize: 13, fontWeight: 'normal', fontFamily: 'monospace' },
      left: 'center',
      top: 10,
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: '#182234',
      borderColor: '#334155',
      textStyle: { color: '#f8fafc' },
    },
    grid: {
      top: '50px',
      bottom: '30px',
      left: '45px',
      right: '25px',
    },
    xAxis: {
      type: 'category',
      data: categories,
      axisLabel: { color: '#94a3b8', fontSize: 11, fontFamily: 'monospace' },
      axisLine: { lineStyle: { color: '#334155' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#1e293b' } },
      axisLabel: { color: '#94a3b8', fontSize: 10 },
    },
    series: [
      {
        type: 'bar',
        data: seriesData,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: barColor },
            { offset: 1, color: 'rgba(30, 41, 59, 0.4)' },
          ]),
          borderRadius: [4, 4, 0, 0],
        },
        label: {
          show: true,
          position: 'top',
          color: '#94a3b8',
          fontSize: 10,
          fontFamily: 'monospace',
        },
      },
    ],
  };

  chartInstance.setOption(option);
}

watch(
  () => [props.data, props.metricType],
  () => {
    renderChart();
  },
  { deep: true }
);

onMounted(() => {
  renderChart();
  if (chartRef.value) {
    resizeObserver = new ResizeObserver(() => {
      chartInstance?.resize();
    });
    resizeObserver.observe(chartRef.value);
  }
});

onUnmounted(() => {
  resizeObserver?.disconnect();
  chartInstance?.dispose();
});
</script>

<template>
  <div class="relative w-full h-[260px]">
    <div ref="chartRef" class="w-full h-full"></div>
    <div
      v-if="!data"
      class="absolute inset-0 flex items-center justify-center bg-[#111827]/80 text-[#94a3b8] text-sm font-mono"
    >
      指标分布计算中...
    </div>
  </div>
</template>
