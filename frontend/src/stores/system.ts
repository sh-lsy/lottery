import { defineStore } from 'pinia';
import { ref } from 'vue';
import { getHealth } from '../api/system';
import { getAdaptiveStatus } from '../api/adaptive';
import { getLatestDraw } from '../api/history';
import type { SystemHealth } from '../types/api';
import type { AdaptiveStateResponse } from '../types/adaptive';
import type { DrawRecordItem } from '../types/history';

export const useSystemStore = defineStore('system', () => {
  const isHealthy = ref<boolean>(false);
  const healthData = ref<SystemHealth | null>(null);
  const latestDraw = ref<DrawRecordItem | null>(null);
  const adaptiveState = ref<AdaptiveStateResponse | null>(null);
  const camouflage = ref<boolean>(false);

  async function refreshSystemStatus() {
    try {
      const h = await getHealth();
      healthData.value = h;
      isHealthy.value = h.status === 'healthy';
    } catch {
      isHealthy.value = false;
    }

    try {
      const draw = await getLatestDraw();
      latestDraw.value = draw;
    } catch (e) {
      console.warn('Failed to fetch latest draw', e);
    }

    try {
      const ad = await getAdaptiveStatus();
      adaptiveState.value = ad;
    } catch (e) {
      console.warn('Failed to fetch adaptive status', e);
    }
  }

  function toggleCamouflage() {
    camouflage.value = !camouflage.value;
  }

  return {
    isHealthy,
    healthData,
    latestDraw,
    adaptiveState,
    camouflage,
    refreshSystemStatus,
    toggleCamouflage,
  };
});
