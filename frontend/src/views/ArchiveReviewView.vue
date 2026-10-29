<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import {
  listPredictionBatches,
  getPredictionBatch,
  getPredictDashboard,
  deletePredictionBatch,
  deduplicatePredictionBatches,
} from '../api/predict';
import { verifyIssue } from '../api/backtest';
import { getAdaptiveStatus } from '../api/adaptive';
import type {
  PredictionBatchSummary,
  PredictionBatchDetail,
  PredictDashboardResponse,
} from '../types/predict';
import type { AdaptiveStateResponse } from '../types/adaptive';
import BallBadge from '../components/common/BallBadge.vue';
import MetricCard from '../components/common/MetricCard.vue';
import QuantCard from '../components/common/QuantCard.vue';
import { useSystemStore } from '../stores/system';

const systemStore = useSystemStore();

// States
const loading = ref(false);
const verifying = ref(false);
const deleting = ref(false);
const deduplicating = ref(false);
const dashboard = ref<PredictDashboardResponse | null>(null);
const adaptiveState = ref<AdaptiveStateResponse | null>(null);
const batches = ref<PredictionBatchSummary[]>([]);
const totalBatches = ref(0);
const currentPage = ref(1);
const pageSize = ref(10);
const verifyFilter = ref<string>('ALL'); // ALL, PENDING, VERIFIED

// Selected batch detail for inspector
const selectedBatchDetail = ref<PredictionBatchDetail | null>(null);
const loadingDetail = ref(false);

async function loadDashboard() {
  try {
    const res = await getPredictDashboard();
    dashboard.value = res;
  } catch (e) {
    console.error('Failed to load predict dashboard', e);
  }
}

async function loadAdaptive() {
  try {
    const res = await getAdaptiveStatus();
    adaptiveState.value = res;
  } catch (e) {
    console.error('Failed to load adaptive state', e);
  }
}

async function loadBatches() {
  loading.value = true;
  try {
    const statusParam = verifyFilter.value === 'ALL' ? undefined : verifyFilter.value;
    const res = await listPredictionBatches({
      page: currentPage.value,
      page_size: pageSize.value,
      verify_status: statusParam,
    });
    batches.value = res.items;
    totalBatches.value = res.total;

    // Auto select first batch if none selected or current selected is not in items
    if (batches.value.length > 0) {
      const exists = batches.value.some((b) => b.id === selectedBatchDetail.value?.id);
      if (!selectedBatchDetail.value || !exists) {
        selectBatch(batches.value[0].id);
      }
    } else {
      selectedBatchDetail.value = null;
    }
  } catch (e) {
    console.error('Failed to list batches', e);
  } finally {
    loading.value = false;
  }
}

async function handleRefresh() {
  await Promise.all([loadDashboard(), loadAdaptive(), loadBatches()]);
  ElMessage.success('档案与统计数据已刷新');
}

async function handleDeduplicate() {
  deduplicating.value = true;
  try {
    const res = await deduplicatePredictionBatches();
    ElMessage.success(res.message);
    await handleRefresh();
  } catch {
    ElMessage.error('去重清理失败');
  } finally {
    deduplicating.value = false;
  }
}

async function handleDeleteBatch(batchId: number) {
  deleting.value = true;
  try {
    const res = await deletePredictionBatch(batchId);
    ElMessage.success(res.message);
    selectedBatchDetail.value = null;
    await Promise.all([loadDashboard(), loadBatches()]);
  } catch {
    ElMessage.error(`删除批次 #${batchId} 失败`);
  } finally {
    deleting.value = false;
  }
}

async function selectBatch(batchId: number) {
  loadingDetail.value = true;
  try {
    const detail = await getPredictionBatch(batchId);
    selectedBatchDetail.value = detail;
  } catch {
    ElMessage.error(`获取批次 #${batchId} 详情失败`);
  } finally {
    loadingDetail.value = false;
  }
}

async function handleVerify(issueNo: string) {
  verifying.value = true;
  try {
    await verifyIssue(issueNo, true);
    ElMessage.success(`期号 ${issueNo} 核奖校验完成！自适应反馈闭环已更新`);
    await Promise.all([loadDashboard(), loadAdaptive(), loadBatches()]);
    if (selectedBatchDetail.value) {
      selectBatch(selectedBatchDetail.value.id);
    }
    systemStore.refreshSystemStatus();
  } catch {
    ElMessage.error(`期号 ${issueNo} 核奖失败，请确认该期是否已有官方开奖`);
  } finally {
    verifying.value = false;
  }
}

function getPrizeName(level: number): string {
  switch (level) {
    case 1: return '一等奖';
    case 2: return '二等奖';
    case 3: return '三等奖';
    case 4: return '四等奖';
    case 5: return '五等奖';
    case 6: return '六等奖';
    default: return '未中奖';
  }
}

function isHitRed(ball: number, hitRedNumbers: number[]): boolean {
  return hitRedNumbers.includes(ball);
}

onMounted(() => {
  loadDashboard();
  loadAdaptive();
  loadBatches();
});
</script>

<template>
  <div class="space-y-6">
    <!-- Executive Stats Header -->
    <div class="grid grid-cols-1 md:grid-cols-5 gap-4">
      <MetricCard
        label="预测批次总数 / 注数"
        :value="`${dashboard?.total_batches || 0} 批 / ${dashboard?.total_notes || 0} 注`"
        sub-value="5 注 / 批次"
        color="default"
      />
      <MetricCard
        label="虚拟总投入 vs 奖金"
        :value="`¥${dashboard?.total_investment || 0} / ¥${dashboard?.total_returns || 0}`"
        :sub-value="`净额: ¥${dashboard?.net_profit || 0}`"
        :color="(dashboard?.net_profit || 0) >= 0 ? 'emerald' : 'rose'"
      />
      <MetricCard
        label="保本率 (Break-Even Rate)"
        :value="`${((dashboard?.break_even_rate || 0) * 100).toFixed(1)}%`"
        :sub-value="`保本批次: ${dashboard?.break_even_batches || 0}`"
        color="cyan"
      />
      <MetricCard
        label="蓝球单注命中率"
        :value="`${((dashboard?.blue_hit_rate || 0) * 100).toFixed(1)}%`"
        sub-value="理论基准: 6.25%"
        color="cyan"
      />
      <MetricCard
        label="自适应演进状态"
        :value="adaptiveState?.blue_mode || 'CONCENTRATED'"
        :sub-value="`亏损回撤: ${adaptiveState?.consecutive_deficit_count || 0} 期`"
        :color="(adaptiveState?.consecutive_deficit_count || 0) >= 3 ? 'amber' : 'emerald'"
      />
    </div>

    <!-- Main Review Layout -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <!-- Left: Batch Timeline List (5 cols) -->
      <div class="lg:col-span-5 space-y-4">
        <QuantCard title="历史预测批次档案 (Prediction Batches)">
          <template #action>
            <div class="flex items-center space-x-2">
              <!-- Filter Tabs -->
              <div class="bg-[#111827] p-0.5 rounded-lg border border-[#334155] flex text-xs font-mono">
                <button
                  @click="verifyFilter = 'ALL'; currentPage = 1; loadBatches()"
                  class="px-2 py-1 rounded transition-all"
                  :class="verifyFilter === 'ALL' ? 'bg-[#00d2d3] text-[#0b0f19] font-bold' : 'text-[#94a3b8]'"
                >
                  全部
                </button>
                <button
                  @click="verifyFilter = 'PENDING'; currentPage = 1; loadBatches()"
                  class="px-2 py-1 rounded transition-all"
                  :class="verifyFilter === 'PENDING' ? 'bg-[#f59e0b] text-[#0b0f19] font-bold' : 'text-[#94a3b8]'"
                >
                  待开奖
                </button>
                <button
                  @click="verifyFilter = 'VERIFIED'; currentPage = 1; loadBatches()"
                  class="px-2 py-1 rounded transition-all"
                  :class="verifyFilter === 'VERIFIED' ? 'bg-[#10b981] text-[#0b0f19] font-bold' : 'text-[#94a3b8]'"
                >
                  已核验
                </button>
              </div>

              <!-- Refresh Button -->
              <el-button
                size="small"
                type="info"
                plain
                :loading="loading"
                @click="handleRefresh"
                class="!font-bold !text-xs !px-2.5"
                title="重新载入最新预测批次档案"
              >
                🔄 刷新
              </el-button>

              <!-- Deduplicate Button -->
              <el-button
                size="small"
                type="warning"
                plain
                :loading="deduplicating"
                @click="handleDeduplicate"
                class="!font-bold !text-xs !px-2.5"
                title="扫描并清理一模一样的重复预测方案，保留每组唯一一份"
              >
                🧹 一键去重
              </el-button>
            </div>
          </template>

          <!-- Batches List -->
          <div class="space-y-2.5 max-h-[650px] overflow-y-auto pr-1">
            <div
              v-for="b in batches"
              :key="b.id"
              @click="selectBatch(b.id)"
              class="p-3 rounded-lg border cursor-pointer transition-all font-mono"
              :class="[
                selectedBatchDetail?.id === b.id
                  ? 'bg-[#182234] border-[#00d2d3] shadow-[0_0_10px_rgba(0,210,211,0.25)]'
                  : 'bg-[#111827] border-[#1e293b] hover:border-[#334155]'
              ]"
            >
              <div class="flex items-center justify-between text-xs">
                <div class="flex items-center space-x-2">
                  <span class="text-white font-bold text-sm">#{{ b.id }}</span>
                  <span class="text-[#00d2d3] font-bold">{{ b.target_issue }} 期</span>
                </div>
                <span
                  class="px-2 py-0.5 rounded text-[11px] font-bold"
                  :class="b.verify_status === 'VERIFIED' ? 'bg-[#10b981]/20 text-[#10b981] border border-[#10b981]/40' : 'bg-[#f59e0b]/20 text-[#f59e0b] border border-[#f59e0b]/40'"
                >
                  {{ b.verify_status === 'VERIFIED' ? '已核验' : '待开奖' }}
                </span>
              </div>

              <div class="mt-2 flex items-center justify-between text-xs text-[#94a3b8]">
                <span>策略: {{ b.strategy_type }}</span>
                <span>
                  投入: <strong class="text-white">¥{{ b.virtual_cost }}</strong> |
                  收益: <strong :class="b.virtual_reward >= b.virtual_cost ? 'text-[#10b981]' : 'text-[#ff4757]'">¥{{ b.virtual_reward }}</strong>
                </span>
              </div>

              <div v-if="b.verify_status === 'VERIFIED'" class="mt-1 flex items-center justify-between text-xs">
                <span class="text-[#64748b]">最高中奖: {{ getPrizeName(b.best_prize_level) }}</span>
                <span
                  class="font-bold"
                  :class="b.net_profit >= 0 ? 'text-[#10b981]' : 'text-[#ef4444]'"
                >
                  ROI: {{ (b.roi * 100).toFixed(1) }}%
                </span>
              </div>
            </div>

            <div v-if="batches.length === 0 && !loading" class="text-center py-12 text-[#64748b] text-xs font-mono">
              暂无符合条件的预测批次
            </div>
          </div>

          <!-- Pagination -->
          <div class="flex justify-end mt-3">
            <el-pagination
              v-model:current-page="currentPage"
              v-model:page-size="pageSize"
              :total="totalBatches"
              layout="prev, pager, next"
              small
              background
              @current-change="loadBatches"
            />
          </div>
        </QuantCard>
      </div>

      <!-- Right: Detailed 5-Note Glowing Inspection Card (7 cols) -->
      <div class="lg:col-span-7 space-y-4">
        <QuantCard
          v-if="selectedBatchDetail"
          :title="`批次 #${selectedBatchDetail.id} - 目标开奖期号: ${selectedBatchDetail.target_issue}`"
        >
          <template #action>
            <div class="flex items-center space-x-2">
              <el-button
                v-if="selectedBatchDetail.verify_status === 'PENDING'"
                type="primary"
                size="small"
                :loading="verifying"
                @click="handleVerify(selectedBatchDetail.target_issue)"
                class="!bg-[#00d2d3] !border-[#00d2d3] !text-[#0b0f19] !font-bold"
              >
                ⚡ 立即核奖比对
              </el-button>

              <el-popconfirm
                :title="`确认删除批次 #${selectedBatchDetail.id}（目标 ${selectedBatchDetail.target_issue} 期）及其 5 注记录？`"
                confirm-button-text="确定删除"
                cancel-button-text="取消"
                confirm-button-type="danger"
                @confirm="handleDeleteBatch(selectedBatchDetail.id)"
              >
                <template #reference>
                  <el-button
                    type="danger"
                    size="small"
                    plain
                    :loading="deleting"
                    class="!font-bold"
                  >
                    🗑️ 删除批次
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
          </template>

          <div class="space-y-4 font-mono">
            <!-- Official Authentic Draw Banner (if verified) -->
            <div
              v-if="selectedBatchDetail.actual_draw"
              class="p-3.5 rounded-lg bg-[#111827] border border-[#00d2d3]/50 shadow-[0_0_12px_rgba(0,210,211,0.15)] flex flex-col md:flex-row md:items-center justify-between gap-3"
            >
              <div>
                <div class="text-xs text-[#94a3b8]">本期官方真实开奖结果</div>
                <div class="text-sm font-bold text-white mt-0.5">
                  {{ selectedBatchDetail.actual_draw.issue_no }} ({{ selectedBatchDetail.actual_draw.draw_date }})
                </div>
              </div>
              <div class="flex items-center space-x-1.5">
                <BallBadge
                  v-for="r in selectedBatchDetail.actual_draw.reds"
                  :key="r"
                  :num="r"
                  type="red"
                  size="md"
                />
                <span class="text-[#64748b] font-bold px-1">+</span>
                <BallBadge
                  :num="selectedBatchDetail.actual_draw.blue"
                  type="blue"
                  size="md"
                />
              </div>
            </div>

            <div
              v-else
              class="p-3 rounded-lg bg-[#111827] border border-[#334155] text-xs text-[#94a3b8] flex items-center justify-between"
            >
              <span>官方开奖尚未产生或未核验，开奖后点击上方「立即核奖比对」</span>
              <span class="text-[#f59e0b] font-bold">待开奖</span>
            </div>

            <!-- 5-Note Comparison Cards with Glowing Hit Balls -->
            <div>
              <div class="text-xs text-[#94a3b8] mb-2 font-bold flex items-center justify-between">
                <span>5 注推演方案逐注比对:</span>
                <span class="text-[11px] text-[#64748b]">命中红球霓虹红发光 / 命中蓝球电光蓝发光</span>
              </div>

              <div class="space-y-2.5">
                <div
                  v-for="item in selectedBatchDetail.items"
                  :key="item.note_index"
                  class="p-3 rounded-lg bg-[#111827] border border-[#1e293b] flex flex-col md:flex-row md:items-center justify-between gap-3 hover:border-[#334155] transition-all"
                >
                  <div class="flex items-center space-x-3">
                    <span class="w-6 h-6 rounded bg-[#1e293b] text-[#94a3b8] text-xs font-bold flex items-center justify-center">
                      {{ item.note_index }}
                    </span>

                    <!-- Red Balls with hit glow -->
                    <div class="flex items-center space-x-1.5">
                      <BallBadge
                        v-for="r in item.reds"
                        :key="r"
                        :num="r"
                        type="red"
                        :hit="item.is_verified && isHitRed(r, item.hit_red_numbers)"
                        :missed="item.is_verified && !isHitRed(r, item.hit_red_numbers)"
                        size="md"
                      />
                    </div>

                    <span class="text-[#64748b] font-bold">+</span>

                    <!-- Blue Ball with hit glow -->
                    <BallBadge
                      :num="item.blue"
                      type="blue"
                      :hit="item.is_verified && item.hit_blue"
                      :missed="item.is_verified && !item.hit_blue"
                      size="md"
                    />
                  </div>

                  <!-- Prize Badge & Return -->
                  <div class="flex items-center space-x-2 text-xs">
                    <span
                      class="px-2.5 py-1 rounded font-bold"
                      :class="[
                        item.prize_level > 0 && item.prize_level <= 4 ? 'bg-[#ff4757]/20 text-[#ff4757] border border-[#ff4757]/40 shadow-[0_0_8px_rgba(255,71,87,0.4)]' :
                        item.prize_level === 5 ? 'bg-[#10b981]/20 text-[#10b981] border border-[#10b981]/40' :
                        item.prize_level === 6 ? 'bg-[#00d2d3]/20 text-[#00d2d3] border border-[#00d2d3]/40' :
                        'bg-[#1e293b] text-[#64748b]'
                      ]"
                    >
                      {{ item.is_verified ? `${getPrizeName(item.prize_level)} (¥${item.prize_amount})` : '待开奖' }}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Post Reflection Markdown Box -->
            <div v-if="selectedBatchDetail.post_reflection_md" class="mt-4">
              <div class="text-xs text-[#94a3b8] mb-1 font-bold">
                🎯 自适应复盘反思与特征偏差 (Adaptive Reflection & Deviation):
              </div>
              <div class="prose prose-invert max-w-none text-xs text-[#cbd5e1] font-mono whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto p-3 rounded bg-[#111827] border border-[#1e293b]">
                {{ selectedBatchDetail.post_reflection_md }}
              </div>
            </div>
          </div>
        </QuantCard>

        <div
          v-else
          class="h-96 flex flex-col items-center justify-center text-[#64748b] text-sm font-mono"
        >
          从左侧选择一个预测批次查看详细比对
        </div>
      </div>
    </div>
  </div>
</template>
