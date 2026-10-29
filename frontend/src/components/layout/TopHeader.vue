<script setup lang="ts">
import { computed } from 'vue';
import { useSystemStore } from '../../stores/system';
import BallBadge from '../common/BallBadge.vue';

const systemStore = useSystemStore();

const adaptiveMode = computed(() => {
  return systemStore.adaptiveState?.blue_mode || 'CONCENTRATED';
});

const isConcentrated = computed(() => {
  return adaptiveMode.value === 'CONCENTRATED';
});

function formatShortDate(d?: string) {
  if (!d) return '';
  const parts = d.split('-');
  if (parts.length >= 3) {
    return `${parts[1]}-${parts[2]}`;
  }
  return d;
}
</script>

<template>
  <header class="h-16 bg-[#111827] border-b border-[#334155] px-6 flex items-center justify-between select-none">
    <!-- Left: Status tags & Latest Draw -->
    <div class="flex items-center space-x-4">
      <!-- Backend Health Indicator -->
      <div class="flex items-center space-x-2 px-2.5 py-1 rounded-md bg-[#182234] border border-[#334155] text-xs font-mono">
        <span
          class="w-2 h-2 rounded-full inline-block"
          :class="systemStore.isHealthy ? 'bg-[#10b981] shadow-[0_0_8px_#10b981]' : 'bg-[#ef4444] shadow-[0_0_8px_#ef4444]'"
        ></span>
        <span :class="systemStore.isHealthy ? 'text-[#10b981]' : 'text-[#ef4444]'">
          {{ systemStore.isHealthy ? 'API ONLINE' : 'API OFFLINE' }}
        </span>
      </div>

      <!-- Latest Draw Badge -->
      <div
        v-if="systemStore.latestDraw"
        class="hidden md:flex items-center space-x-2 px-3 py-1 rounded-md bg-[#182234] border border-[#334155] text-xs"
      >
        <span class="text-[#94a3b8] font-mono">最新开奖:</span>
        <span class="font-bold text-[#f8fafc] font-mono">
          {{ systemStore.latestDraw.issue_no }}
          <span v-if="systemStore.latestDraw.draw_date" class="text-xs text-[#94a3b8] font-normal ml-0.5">
            ({{ formatShortDate(systemStore.latestDraw.draw_date) }})
          </span>
        </span>
        <div class="flex items-center space-x-1 pl-1">
          <BallBadge
            v-for="r in systemStore.latestDraw.reds"
            :key="r"
            :num="r"
            type="red"
            size="sm"
          />
          <BallBadge
            :num="systemStore.latestDraw.blue"
            type="blue"
            size="sm"
          />
        </div>
      </div>

      <!-- Adaptive Strategy Mode Badge -->
      <div class="flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-[#182234] border border-[#334155] text-xs font-mono">
        <span class="text-[#94a3b8]">自适应模式:</span>
        <span
          class="px-1.5 py-0.5 rounded text-[11px] font-bold tracking-wider"
          :class="isConcentrated ? 'bg-[#00d2d3]/20 text-[#00d2d3] border border-[#00d2d3]/40' : 'bg-[#f59e0b]/20 text-[#f59e0b] border border-[#f59e0b]/40'"
        >
          {{ isConcentrated ? 'CONCENTRATED (3+2集中)' : 'DISPERSED (5互异分散)' }}
        </span>
      </div>
    </div>

    <!-- Right: Camouflage Switch & Actions -->
    <div class="flex items-center space-x-3">
      <button
        @click="systemStore.toggleCamouflage"
        class="px-3 py-1.5 rounded-lg border border-[#334155] text-xs font-mono text-[#94a3b8] hover:text-[#f8fafc] hover:bg-[#182234] transition-all flex items-center space-x-1.5"
        title="工位伪装模式切换"
      >
        <span>{{ systemStore.camouflage ? '🕶️ 终端伪装中' : '🎭 工位伪装' }}</span>
      </button>

      <button
        @click="systemStore.refreshSystemStatus"
        class="p-1.5 rounded-lg border border-[#334155] text-xs font-mono text-[#94a3b8] hover:text-[#00d2d3] hover:bg-[#182234] transition-all"
        title="刷新状态"
      >
        🔄
      </button>
    </div>
  </header>
</template>
