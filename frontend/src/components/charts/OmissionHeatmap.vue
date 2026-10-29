<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted } from 'vue';
import * as echarts from 'echarts';
import type { OmissionTrendResponse } from '../../types/history';

interface Props {
  omissionData: OmissionTrendResponse | null;
  ballType?: 'red' | 'blue';
}

const props = withDefaults(defineProps<Props>(), {
  omissionData: null,
  ballType: 'red',
});

const chartRef = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

function renderChart() {
  if (!chartRef.value || !props.omissionData) return;

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value, 'dark');
  }

  const issues = props.omissionData.issues; // list of issue strings
  const isRed = props.ballType === 'red';
  const ballCount = isRed ? 33 : 16;
  const ballLabels = Array.from({ length: ballCount }, (_, i) => {
    const num = i + 1;
    return num < 10 ? `0${num}` : `${num}`;
  });

  // Prepare heatmap series data: [x, y, value]
  // x: ball index (0..ballCount-1), y: issue index (0..issues.length-1)
  const heatmapData: [number, number, number][] = [];

  props.omissionData.timeline.forEach((item, yIdx) => {
    const omissions = isRed ? item.red_omissions : item.blue_omissions;
    for (let xIdx = 0; xIdx < ballCount; xIdx++) {
      const ballNumStr = (xIdx + 1).toString();
      const val = omissions[ballNumStr] ?? 0;
      heatmapData.push([xIdx, yIdx, val]);
    }
  });

  const hitColor = isRed ? '#ff4757' : '#00d2d3';

  const option: echarts.EChartsOption = {
    backgroundColor: '#111827',
    tooltip: {
      position: 'top',
      backgroundColor: '#182234',
      borderColor: '#334155',
      textStyle: { color: '#f8fafc', fontSize: 12 },
      formatter: (params: any) => {
        const [xIdx, yIdx, val] = params.data;
        const issue = issues[yIdx];
        const ball = ballLabels[xIdx];
        const status = val === 0 ? '🎯 当期命中' : `遗漏 ${val} 期`;
        return `<div class="font-mono">
          <div class="text-[#94a3b8]">期号: <span class="text-white font-bold">${issue}</span></div>
          <div class="text-[#94a3b8]">${isRed ? '红球' : '蓝球'}: <span class="text-white font-bold">${ball}</span></div>
          <div class="mt-1 font-bold ${val === 0 ? 'text-[#00d2d3]' : 'text-[#f8fafc]'}">${status}</div>
        </div>`;
      },
    },
    grid: {
      top: '40px',
      bottom: '40px',
      left: '70px',
      right: '40px',
    },
    xAxis: {
      type: 'category',
      data: ballLabels,
      splitArea: { show: true, areaStyle: { color: ['rgba(24,34,52,0.3)', 'rgba(17,24,39,0.3)'] } },
      axisLabel: { color: '#94a3b8', fontSize: 11, fontFamily: 'monospace' },
      axisLine: { lineStyle: { color: '#334155' } },
    },
    yAxis: {
      type: 'category',
      data: issues,
      splitArea: { show: true, areaStyle: { color: ['rgba(24,34,52,0.3)', 'rgba(17,24,39,0.3)'] } },
      axisLabel: { color: '#94a3b8', fontSize: 10, fontFamily: 'monospace' },
      axisLine: { lineStyle: { color: '#334155' } },
    },
    visualMap: {
      min: 0,
      max: 20,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: '0px',
      itemWidth: 14,
      itemHeight: 120,
      textStyle: { color: '#94a3b8', fontSize: 10 },
      inRange: {
        color: [hitColor, '#f59e0b', '#dc2626', '#475569', '#1e293b'],
      },
    },
    series: [
      {
        name: isRed ? '红球遗漏' : '蓝球遗漏',
        type: 'heatmap',
        data: heatmapData,
        label: {
          show: true,
          color: '#ffffff',
          fontSize: 9,
          fontFamily: 'monospace',
          formatter: (p: any) => (p.data[2] === 0 ? '★' : `${p.data[2]}`),
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.8)',
          },
        },
      },
    ],
  };

  chartInstance.setOption(option);
}

watch(
  () => [props.omissionData, props.ballType],
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
  <div class="relative w-full h-[450px]">
    <div ref="chartRef" class="w-full h-full"></div>
    <div
      v-if="!omissionData"
      class="absolute inset-0 flex items-center justify-center bg-[#111827]/80 text-[#94a3b8] text-sm font-mono"
    >
      加载遗漏矩阵数据中...
    </div>
  </div>
</template>
