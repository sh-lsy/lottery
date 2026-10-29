<script setup lang="ts">
import { onMounted } from 'vue';
import SidebarNav from './SidebarNav.vue';
import TopHeader from './TopHeader.vue';
import { useSystemStore } from '../../stores/system';

const systemStore = useSystemStore();

onMounted(() => {
  systemStore.refreshSystemStatus();
});
</script>

<template>
  <div class="flex h-screen w-screen overflow-hidden bg-[#0b0f19] text-[#f8fafc]">
    <!-- Left Navigation Sidebar -->
    <SidebarNav />

    <!-- Main Content Area -->
    <div class="flex-1 flex flex-col h-full overflow-hidden">
      <!-- Top Status Header -->
      <TopHeader />

      <!-- Viewport Content Area -->
      <main class="flex-1 overflow-y-auto p-6 bg-[#0b0f19]">
        <router-view />
      </main>
    </div>
  </div>
</template>
