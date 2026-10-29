<script setup lang="ts">
interface Props {
  title?: string;
  subtitle?: string;
  bordered?: boolean;
}

withDefaults(defineProps<Props>(), {
  title: '',
  subtitle: '',
  bordered: true,
});
</script>

<template>
  <div
    class="bg-[#182234] rounded-lg p-4 transition-all duration-200"
    :class="bordered ? 'border border-[#334155]' : ''"
  >
    <div v-if="title || $slots.header" class="flex items-center justify-between pb-3 mb-3 border-b border-[#1e293b]">
      <div>
        <h3 class="text-sm font-semibold tracking-wide text-[#f8fafc] uppercase font-mono">
          <slot name="title">{{ title }}</slot>
        </h3>
        <p v-if="subtitle" class="text-xs text-[#94a3b8] mt-0.5">
          {{ subtitle }}
        </p>
      </div>
      <div v-if="$slots.action" class="flex items-center space-x-2">
        <slot name="action"></slot>
      </div>
    </div>
    <slot></slot>
  </div>
</template>
