<script setup lang="ts">
import { computed } from 'vue';

interface Props {
  num: number | string;
  type: 'red' | 'blue';
  hit?: boolean;
  missed?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

const props = withDefaults(defineProps<Props>(), {
  hit: false,
  missed: false,
  size: 'md',
});

const formattedNum = computed(() => {
  const n = typeof props.num === 'string' ? parseInt(props.num, 10) : props.num;
  if (isNaN(n)) return props.num;
  return n < 10 ? `0${n}` : `${n}`;
});

const sizeClass = computed(() => {
  switch (props.size) {
    case 'sm':
      return 'w-6 h-6 text-xs';
    case 'lg':
      return 'w-10 h-10 text-base font-bold';
    case 'md':
    default:
      return 'w-8 h-8 text-sm font-semibold';
  }
});

const visualClass = computed(() => {
  if (props.missed) {
    return 'ball-missed';
  }
  if (props.type === 'red') {
    return props.hit ? 'ball-red-hit' : 'ball-red-regular';
  } else {
    return props.hit ? 'ball-blue-hit' : 'ball-blue-regular';
  }
});
</script>

<template>
  <span
    class="ball-badge inline-flex items-center justify-center font-mono select-none"
    :class="[sizeClass, visualClass]"
  >
    {{ formattedNum }}
  </span>
</template>
