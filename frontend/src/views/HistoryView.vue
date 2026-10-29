<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import {
  getDrawHistory,
  getLatestDraw,
  getOmissionTrends,
  getDistributions,
  syncHistory,
} from '../api/history';
import type {
  DrawRecordItem,
  OmissionTrendResponse,
  IndicatorDistributionResponse,
} from '../types/history';
import BallBadge from '../components/common/BallBadge.vue';
import MetricCard from '../components/common/MetricCard.vue';
import QuantCard from '../components/common/QuantCard.vue';
import OmissionHeatmap from '../components/charts/OmissionHeatmap.vue';
import IndicatorChart from '../components/charts/IndicatorChart.vue';
import { useSystemStore } from '../stores/system';

const systemStore = useSystemStore();

// Loading states
const loadingTable = ref(false);
const syncing = ref(false);

// Data
const latestDraw = ref<DrawRecordItem | null>(null);
const omissionData = ref<OmissionTrendResponse | null>(null);
const distributionData = ref<IndicatorDistributionResponse | null>(null);
const draws = ref<DrawRecordItem[]>([]);
const totalDraws = ref(0);

// Query controls
const currentPage = ref(1);
const pageSize = ref(20);
const searchBall = ref<number | undefined>(undefined);
const omissionLimit = ref(30);
const heatmapBallType = ref<'red' | 'blue'>('red');
const activeMetricTab = ref<'sum' | 'ac' | 'oddEven' | 'span'>('sum');

async function loadLatest() {
  try {
    const res = await getLatestDraw();
    latestDraw.value = res;
  } catch (e) {
    console.error('Failed to load latest draw', e);
  }
}

async function loadOmissions() {
  try {
    const res = await getOmissionTrends(omissionLimit.value);
    omissionData.value = res;
  } catch (e) {
    console.error('Failed to load omissions', e);
  }
}

async function loadDistributions() {
  try {
    const res = await getDistributions(100);
    distributionData.value = res;
  } catch (e) {
    console.error('Failed to load distributions', e);
  }
}

async function loadDraws() {
  loadingTable.value = true;
  try {
    const res = await getDrawHistory({
      page: currentPage.value,
      page_size: pageSize.value,
      sort_order: 'desc',
      search_ball: searchBall.value,
    });
    draws.value = res.items;
    totalDraws.value = res.total;
  } catch (e) {
    console.error('Failed to load draw history', e);
  } finally {
    loadingTable.value = false;
  }
}

async function handleSync() {
  syncing.value = true;
  try {
    const res = await syncHistory(false);
    ElMessage.success(res.message || '增量开奖数据同步成功！');
    await Promise.all([loadLatest(), loadOmissions(), loadDistributions(), loadDraws()]);
    systemStore.refreshSystemStatus();
  } catch {
    ElMessage.error('增量同步触发失败，请检查网络或后端状态');
  } finally {
    syncing.value = false;
  }
}

function handlePageChange(val: number) {
  currentPage.value = val;
  loadDraws();
}

function formatAmount(val: number): string {
  if (val >= 100000000) {
    return `¥${(val / 100000000).toFixed(2)} 亿`;
  }
  if (val >= 10000) {
    return `¥${(val / 10000).toFixed(1)} 万`;
  }
  return `¥${val}`;
}

onMounted(() => {
  loadLatest();
  loadOmissions();
  loadDistributions();
  loadDraws();
});
</script>

<template>
  <div class="space-y-6">
    <!-- Top KPI Banner -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <MetricCard
        label="最新官方开奖期号"
        :value="latestDraw?.issue_no || '2026122'"
        :sub-value="latestDraw?.draw_date ? String(latestDraw.draw_date) : ''"
        color="cyan"
      />
      <MetricCard
        label="官方奖池滚存基金"
        :value="formatAmount(latestDraw?.pool_amount || 2980000000)"
        sub-value="Jackpot Reserve"
        color="amber"
      />
      <MetricCard
        label="近30期热度 Top 3 红球"
        :value="omissionData?.top3_hot_reds?.map(n => (n < 10 ? '0' + n : n)).join(' , ') || '07, 16, 28'"
        sub-value="Hot Momentum"
        color="rose"
      />
      <MetricCard
        label="当前最大深度遗漏红球"
        :value="omissionData?.top3_cold_reds?.map(n => (n < 10 ? '0' + n : n)).join(' , ') || '11, 23, 31'"
        sub-value="Deep Reversion"
        color="default"
      />
    </div>

    <!-- Omission Heatmap Matrix Panel -->
    <QuantCard title="全景遗漏热力矩阵 (Omission Heatmap Matrix)">
      <template #action>
        <div class="flex items-center space-x-3">
          <!-- Red / Blue Switch -->
          <div class="bg-[#111827] p-0.5 rounded-lg border border-[#334155] flex">
            <button
              @click="heatmapBallType = 'red'"
              class="px-3 py-1 rounded text-xs font-mono transition-all"
              :class="heatmapBallType === 'red' ? 'bg-[#ff4757] text-white font-bold' : 'text-[#94a3b8] hover:text-white'"
            >
              红球 (33)
            </button>
            <button
              @click="heatmapBallType = 'blue'"
              class="px-3 py-1 rounded text-xs font-mono transition-all"
              :class="heatmapBallType === 'blue' ? 'bg-[#00d2d3] text-[#0b0f19] font-bold' : 'text-[#94a3b8] hover:text-white'"
            >
              蓝球 (16)
            </button>
          </div>

          <!-- Issues limit selector -->
          <el-select
            v-model="omissionLimit"
            @change="loadOmissions"
            size="small"
            class="w-28 !bg-[#111827]"
          >
            <el-option :value="30" label="近 30 期" />
            <el-option :value="50" label="近 50 期" />
            <el-option :value="100" label="近 100 期" />
          </el-select>
        </div>
      </template>

      <div class="containment-chart">
        <OmissionHeatmap :omission-data="omissionData" :ball-type="heatmapBallType" />
      </div>
    </QuantCard>

    <!-- Indicators Distribution Panel -->
    <QuantCard title="核心量化指标分布 (Mathematical Indicators Distribution)">
      <template #action>
        <div class="flex items-center space-x-1 bg-[#111827] p-0.5 rounded-lg border border-[#334155]">
          <button
            @click="activeMetricTab = 'sum'"
            class="px-2.5 py-1 rounded text-xs font-mono"
            :class="activeMetricTab === 'sum' ? 'bg-[#3b82f6] text-white font-semibold' : 'text-[#94a3b8]'"
          >
            和值 (Sum)
          </button>
          <button
            @click="activeMetricTab = 'ac'"
            class="px-2.5 py-1 rounded text-xs font-mono"
            :class="activeMetricTab === 'ac' ? 'bg-[#10b981] text-white font-semibold' : 'text-[#94a3b8]'"
          >
            AC值 (AC)
          </button>
          <button
            @click="activeMetricTab = 'oddEven'"
            class="px-2.5 py-1 rounded text-xs font-mono"
            :class="activeMetricTab === 'oddEven' ? 'bg-[#ff4757] text-white font-semibold' : 'text-[#94a3b8]'"
          >
            奇偶比 (Odd:Even)
          </button>
          <button
            @click="activeMetricTab = 'span'"
            class="px-2.5 py-1 rounded text-xs font-mono"
            :class="activeMetricTab === 'span' ? 'bg-[#f59e0b] text-white font-semibold' : 'text-[#94a3b8]'"
          >
            跨度 (Span)
          </button>
        </div>
      </template>

      <div class="containment-chart">
        <IndicatorChart :data="distributionData" :metric-type="activeMetricTab" />
      </div>
    </QuantCard>

    <!-- Paginated Draw Records Table -->
    <QuantCard title="官方真实历史开奖记录 (Historical Draws)">
      <template #action>
        <div class="flex items-center space-x-3">
          <!-- Search by ball -->
          <el-input-number
            v-model="searchBall"
            :min="1"
            :max="33"
            placeholder="搜索包含号码"
            size="small"
            class="w-36"
            @change="loadDraws"
          />

          <!-- Sync Trigger Button -->
          <el-button
            type="primary"
            size="small"
            :loading="syncing"
            @click="handleSync"
            class="!bg-[#00d2d3] !border-[#00d2d3] !text-[#0b0f19] !font-bold"
          >
            ⚡ 增量同步最新开奖
          </el-button>
        </div>
      </template>

      <div class="overflow-x-auto rounded border border-[#1e293b]">
        <table class="w-full text-left text-xs font-mono border-collapse">
          <thead class="bg-[#111827] text-[#94a3b8] border-b border-[#334155]">
            <tr>
              <th class="py-3 px-4">期号</th>
              <th class="py-3 px-4">开奖日期</th>
              <th class="py-3 px-4">红球序列 (6)</th>
              <th class="py-3 px-4">蓝球 (1)</th>
              <th class="py-3 px-4 text-center">和值</th>
              <th class="py-3 px-4 text-center">AC值</th>
              <th class="py-3 px-4 text-center">奇偶</th>
              <th class="py-3 px-4 text-center">跨度</th>
              <th class="py-3 px-4 text-right">一等奖 (注数/奖金)</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#1e293b]">
            <tr
              v-for="d in draws"
              :key="d.id"
              class="hover:bg-[#1e293b]/50 transition-colors"
            >
              <td class="py-2.5 px-4 font-bold text-white">{{ d.issue_no }}</td>
              <td class="py-2.5 px-4 text-[#94a3b8]">{{ d.draw_date }} (周{{ d.weekday }})</td>
              <td class="py-2.5 px-4">
                <div class="flex items-center space-x-1.5">
                  <BallBadge
                    v-for="r in d.reds"
                    :key="r"
                    :num="r"
                    type="red"
                    size="sm"
                  />
                </div>
              </td>
              <td class="py-2.5 px-4">
                <BallBadge :num="d.blue" type="blue" size="sm" />
              </td>
              <td class="py-2.5 px-4 text-center font-bold text-[#f8fafc]">
                {{ d.sum_red ?? d.metrics?.sum_red ?? '-' }}
              </td>
              <td class="py-2.5 px-4 text-center text-[#00d2d3]">
                {{ d.ac_value ?? d.metrics?.ac_value ?? '-' }}
              </td>
              <td class="py-2.5 px-4 text-center text-[#94a3b8]">
                {{ d.odd_count !== null && d.odd_count !== undefined ? `${d.odd_count}:${6 - d.odd_count}` : (d.metrics ? `${d.metrics.odd_count}:${6 - d.metrics.odd_count}` : '-') }}
              </td>
              <td class="py-2.5 px-4 text-center text-[#94a3b8]">
                {{ d.metrics?.span_red ?? (d.reds.length ? d.reds[d.reds.length-1] - d.reds[0] : '-') }}
              </td>
              <td class="py-2.5 px-4 text-right">
                <span class="text-[#f59e0b] font-bold">{{ d.first_prize_num }} 注</span>
                <span class="text-[#64748b] text-[11px] ml-1.5">({{ formatAmount(d.first_prize_amount) }})</span>
              </td>
            </tr>
            <tr v-if="draws.length === 0 && !loadingTable">
              <td colspan="9" class="text-center py-8 text-[#64748b]">暂无历史开奖记录</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination Controls -->
      <div class="flex justify-end mt-4">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="totalDraws"
          layout="total, prev, pager, next"
          background
          @current-change="handlePageChange"
        />
      </div>
    </QuantCard>
  </div>
</template>
