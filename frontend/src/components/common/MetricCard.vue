<script setup lang="ts">
interface Props {
  label: string;
  value: string | number;
  subValue?: string;
  trend?: 'up' | 'down' | 'neutral';
  color?: 'default' | 'cyan' | 'emerald' | 'amber' | 'rose';
}

withDefaults(defineProps<Props>(), {
  subValue: '',
  trend: 'neutral',
  color: 'default',
});
</script>

<template>
  <div class="bg-[#111827] border border-[#334155] rounded-lg p-3 flex flex-col justify-between">
    <div class="text-xs text-[#94a3b8] font-mono tracking-wider truncate">
      {{ label }}
    </div>
    <div class="flex items-baseline justify-between mt-2">
      <div
        class="text-xl font-bold font-mono tracking-tight"
        :class="{
          'text-[#f8fafc]': color === 'default',
          'text-[#00d2d3]': color === 'cyan',
          'text-[#10b981]': color === 'emerald',
          'text-[#f59e0b]': color === 'amber',
          'text-[#ff4757]': color === 'rose',
        }"
      >
        {{ value }}
      </div>
      <div v-if="subValue" class="text-xs text-[#64748b] font-mono">
        {{ subValue }}
      </div>
    </div>
  </div>
</template>
