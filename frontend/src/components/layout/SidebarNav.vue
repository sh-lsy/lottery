<script setup lang="ts">
import { useRoute } from 'vue-router';
import { computed } from 'vue';
import { useSystemStore } from '../../stores/system';

const route = useRoute();
const systemStore = useSystemStore();

const navItems = [
  {
    path: '/history',
    name: '走势看板',
    sub: 'History & Trend',
    icon: '📊',
    altName: 'P-Seq 序列矩阵',
  },
  {
    path: '/predict',
    name: '预测实验',
    sub: 'AI Prediction Lab',
    icon: '🧪',
    altName: '多因子推演',
  },
  {
    path: '/archive',
    name: '预测档案',
    sub: 'Archive & Review',
    icon: '📜',
    altName: '回测实盘复盘',
  },
  {
    path: '/sandbox',
    name: '碰撞沙盒',
    sub: 'Collision Sandbox',
    icon: '⚡',
    altName: '历史穿透碰撞',
  },
];

const isCurrent = (path: string) => route.path === path;
</script>

<template>
  <aside class="w-64 bg-[#111827] border-r border-[#334155] flex flex-col justify-between select-none">
    <div>
      <!-- Brand Logo / Terminal ID -->
      <div class="h-16 px-5 flex items-center space-x-3 border-b border-[#334155]">
        <div class="w-9 h-9 rounded-lg bg-gradient-to-br from-[#ff4757] to-[#00d2d3] flex items-center justify-center shadow-lg">
          <span class="text-white font-black text-lg">⚡</span>
        </div>
        <div>
          <div class="text-sm font-bold tracking-wider text-[#f8fafc] font-mono">
            {{ systemStore.camouflage ? 'QUANT-TERMINAL' : 'SSQ-QUANT' }}
          </div>
          <div class="text-[10px] text-[#94a3b8] font-mono tracking-widest uppercase">
            Discrete Seq Lab v2.0
          </div>
        </div>
      </div>

      <!-- Navigation Links -->
      <nav class="p-3 space-y-1.5">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="flex items-center px-3.5 py-3 rounded-lg transition-all duration-200 group relative"
          :class="[
            isCurrent(item.path)
              ? 'bg-[#182234] text-[#00d2d3] border-l-4 border-[#00d2d3] font-semibold shadow-inner'
              : 'text-[#94a3b8] hover:bg-[#182234]/60 hover:text-[#f8fafc]'
          ]"
        >
          <span class="text-lg mr-3 group-hover:scale-110 transition-transform">{{ item.icon }}</span>
          <div class="flex-1 truncate">
            <div class="text-sm tracking-wide">
              {{ systemStore.camouflage ? item.altName : item.name }}
            </div>
            <div class="text-[10px] text-[#64748b] font-mono tracking-wider">
              {{ item.sub }}
            </div>
          </div>
          <div
            v-if="isCurrent(item.path)"
            class="w-1.5 h-1.5 rounded-full bg-[#00d2d3] shadow-[0_0_6px_#00d2d3]"
          ></div>
        </router-link>
      </nav>
    </div>

    <!-- Bottom Terminal Metadata -->
    <div class="p-4 border-t border-[#334155] bg-[#0b0f19]/40 text-xs text-[#64748b] font-mono">
      <div class="flex items-center justify-between">
        <span>Engine:</span>
        <span class="text-[#00d2d3] font-medium">Local-Offline</span>
      </div>
      <div class="flex items-center justify-between mt-1">
        <span>Draws Cache:</span>
        <span class="text-[#cbd5e1]">{{ systemStore.healthData?.database?.total_draws || '3500+' }}</span>
      </div>
    </div>
  </aside>
</template>
