<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { ElMessage } from 'element-plus';
import { generatePrediction, savePrediction } from '../api/predict';
import type {
  PredictionGenerateRequest,
  PredictionGenerateResponse,
  PredictionNoteItem,
} from '../types/predict';
import BallBadge from '../components/common/BallBadge.vue';
import QuantCard from '../components/common/QuantCard.vue';
import { useSystemStore } from '../stores/system';

const systemStore = useSystemStore();

const generating = ref(false);
const saving = ref(false);

// Form parameters
const targetIssue = ref<string>('');
const strategyType = ref<string>('CONCENTRATED_BREAK_EVEN');
const adaptiveEnabled = ref<boolean>(true);
const sumRange = ref<[number, number]>([75, 135]);
const acMin = ref<number>(6);
const spanRange = ref<[number, number]>([18, 30]);
const oddCounts = ref<number[]>([2, 3, 4]);

// Prediction Output
const result = ref<PredictionGenerateResponse | null>(null);
const savedBatchId = ref<number | null>(null);

const strategies = [
  {
    key: 'CONCENTRATED_BREAK_EVEN',
    name: '集中保本策略 (3+2 Blue)',
    desc: '3注命中Top-1蓝保本盈利(+50% ROI)，2注命中Top-2蓝完全保本(0% ROI)。',
  },
  {
    key: 'DISPERSED_BASELINE',
    name: '互异分散策略 (5-Distinct)',
    desc: '覆盖5个互异蓝球(31.25%高概率覆盖)，牺牲超额回报追求稳定防御。',
  },
  {
    key: 'STAT_FILTER',
    name: '统计过滤策略 (Balanced 2+2+1)',
    desc: '严格匹配高频AC值、跨度区间、奇偶配比与无连号/单连号特征。',
  },
  {
    key: 'ML_PROB',
    name: '马尔可夫+冷热集成 (Ensemble ML)',
    desc: '一阶转移矩阵与自适应动量权重融合，动态捕捉状态突变概率。',
  },
];

async function handleGenerate() {
  generating.value = true;
  savedBatchId.value = null;

  const req: PredictionGenerateRequest = {
    target_issue: targetIssue.value ? targetIssue.value : undefined,
    strategy_type: strategyType.value,
    sum_min: sumRange.value[0],
    sum_max: sumRange.value[1],
    ac_min: acMin.value,
    span_min: spanRange.value[0],
    span_max: spanRange.value[1],
    odd_counts: oddCounts.value,
    adaptive_enabled: adaptiveEnabled.value,
    save_to_db: false,
  };

  try {
    const res = await generatePrediction(req);
    result.value = res;
    if (!targetIssue.value) {
      targetIssue.value = res.target_issue;
    }
    ElMessage.success(`推演成功！已生成目标期 ${res.target_issue} 的 5 注量化候选方案`);
  } catch {
    ElMessage.error('推演生成失败，请确认后端连接');
  } finally {
    generating.value = false;
  }
}

async function handleSave() {
  if (!result.value) return;
  saving.value = true;

  try {
    const res = await savePrediction({
      target_issue: result.value.target_issue,
      strategy_type: result.value.strategy_type,
      model_name: result.value.model_name,
      filter_params: result.value.filter_params,
      ai_reasoning_md: result.value.ai_reasoning_md,
      notes: result.value.notes,
      virtual_cost: 10,
    });
    savedBatchId.value = res.batch_id;
    ElMessage.success(`方案已持久化入库！批次 ID: #${res.batch_id}`);
    systemStore.refreshSystemStatus();
  } catch {
    ElMessage.error('保存方案失败');
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  // auto trigger once on initial load
  handleGenerate();
});
</script>

<template>
  <div class="space-y-6">
    <!-- Top Configuration & Simulation Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <!-- Left Config Controls (4 cols) -->
      <div class="lg:col-span-5 space-y-5">
        <QuantCard title="量化推演参数配置 (Strategy & Guardrails)">
          <div class="space-y-4 text-xs font-mono">
            <!-- Target Issue Input -->
            <div>
              <label class="block text-[#94a3b8] mb-1">推演目标期号 (Target Issue)</label>
              <el-input
                v-model="targetIssue"
                placeholder="留空自动顺延最新一期 (如 2026123)"
                class="!bg-[#111827]"
              />
            </div>

            <!-- Strategy Selection -->
            <div>
              <label class="block text-[#94a3b8] mb-1.5">核心生成策略模式</label>
              <div class="space-y-2">
                <div
                  v-for="s in strategies"
                  :key="s.key"
                  @click="strategyType = s.key"
                  class="p-2.5 rounded-lg border cursor-pointer transition-all"
                  :class="[
                    strategyType === s.key
                      ? 'bg-[#182234] border-[#00d2d3] shadow-[0_0_8px_rgba(0,210,211,0.2)]'
                      : 'bg-[#111827] border-[#334155] hover:border-[#475569]'
                  ]"
                >
                  <div class="flex items-center justify-between">
                    <span class="font-bold text-[#f8fafc] text-xs">{{ s.name }}</span>
                    <span
                      v-if="strategyType === s.key"
                      class="w-2 h-2 rounded-full bg-[#00d2d3]"
                    ></span>
                  </div>
                  <p class="text-[11px] text-[#94a3b8] mt-1 font-sans leading-tight">
                    {{ s.desc }}
                  </p>
                </div>
              </div>
            </div>

            <!-- Adaptive Feedback Toggle -->
            <div class="p-3 bg-[#111827] border border-[#334155] rounded-lg flex items-center justify-between">
              <div>
                <div class="font-bold text-[#f8fafc]">自适应策略自我进化</div>
                <div class="text-[11px] text-[#94a3b8]">根据近期开奖偏差自动平移冷热权重</div>
              </div>
              <el-switch v-model="adaptiveEnabled" active-color="#00d2d3" />
            </div>

            <!-- Sum Range Slider -->
            <div>
              <div class="flex justify-between text-[#94a3b8] mb-1">
                <span>和值过滤区间 (Sum):</span>
                <span class="text-[#00d2d3] font-bold">[{{ sumRange[0] }}, {{ sumRange[1] }}]</span>
              </div>
              <el-slider
                v-model="sumRange"
                range
                :min="60"
                :max="150"
                :step="5"
              />
            </div>

            <!-- AC Min Slider -->
            <div>
              <div class="flex justify-between text-[#94a3b8] mb-1">
                <span>最低 AC 值复杂度 (AC Min):</span>
                <span class="text-[#00d2d3] font-bold">≥ {{ acMin }}</span>
              </div>
              <el-slider
                v-model="acMin"
                :min="4"
                :max="9"
                :step="1"
              />
            </div>

            <!-- Span Range Slider -->
            <div>
              <div class="flex justify-between text-[#94a3b8] mb-1">
                <span>跨度区间 (Span):</span>
                <span class="text-[#00d2d3] font-bold">[{{ spanRange[0] }}, {{ spanRange[1] }}]</span>
              </div>
              <el-slider
                v-model="spanRange"
                range
                :min="10"
                :max="32"
                :step="1"
              />
            </div>

            <!-- Odd counts check -->
            <div>
              <label class="block text-[#94a3b8] mb-1">允许奇数个数 (Odd Count):</label>
              <el-checkbox-group v-model="oddCounts">
                <el-checkbox :label="2">2奇 (2:4)</el-checkbox>
                <el-checkbox :label="3">3奇 (3:3)</el-checkbox>
                <el-checkbox :label="4">4奇 (4:2)</el-checkbox>
              </el-checkbox-group>
            </div>

            <!-- Simulation Execution Button -->
            <div class="pt-2">
              <el-button
                type="primary"
                size="large"
                class="w-full !bg-gradient-to-r !from-[#00d2d3] !to-[#0284c7] !border-none !text-[#0b0f19] !font-bold !h-12 !text-sm tracking-wider shadow-lg"
                :loading="generating"
                @click="handleGenerate"
              >
                ⚡ 启动离线量化推演 (Pure Math Engine)
              </el-button>
            </div>
          </div>
        </QuantCard>
      </div>

      <!-- Right Output & Candidate Preview (7 cols) -->
      <div class="lg:col-span-7 space-y-5">
        <!-- 5 Notes Display -->
        <QuantCard title="候选 5 注量化模拟号码方案 (Candidate 5 Notes)">
          <template #action>
            <div class="flex items-center space-x-2">
              <span class="text-xs text-[#94a3b8] font-mono">虚拟投注: 5注共 ¥10</span>
              <el-button
                v-if="result"
                type="success"
                size="small"
                :loading="saving"
                :disabled="savedBatchId !== null"
                @click="handleSave"
                class="!bg-[#10b981] !border-[#10b981] !font-bold"
              >
                {{ savedBatchId ? `已保存 (#${savedBatchId})` : '💾 保存方案至档案' }}
              </el-button>
            </div>
          </template>

          <div v-if="result" class="space-y-3 font-mono">
            <div
              v-for="note in result.notes"
              :key="note.note_index"
              class="p-3.5 bg-[#111827] border border-[#334155] rounded-lg flex flex-col md:flex-row md:items-center justify-between gap-3 hover:border-[#00d2d3]/50 transition-all"
            >
              <div class="flex items-center space-x-3">
                <span class="w-6 h-6 rounded bg-[#1e293b] text-[#94a3b8] text-xs font-bold flex items-center justify-center">
                  {{ note.note_index }}
                </span>
                <!-- Red Balls -->
                <div class="flex items-center space-x-1.5">
                  <BallBadge
                    v-for="r in note.reds"
                    :key="r"
                    :num="r"
                    type="red"
                    size="md"
                  />
                </div>
                <!-- Plus separator -->
                <span class="text-[#64748b] font-bold">+</span>
                <!-- Blue Ball -->
                <BallBadge
                  :num="note.blue"
                  type="blue"
                  size="md"
                />
              </div>

              <!-- Metrics Pills -->
              <div class="flex items-center space-x-2 text-xs">
                <span class="px-2 py-0.5 rounded bg-[#182234] border border-[#334155] text-[#94a3b8]">
                  和: <strong class="text-[#f8fafc]">{{ note.sum_red }}</strong>
                </span>
                <span class="px-2 py-0.5 rounded bg-[#182234] border border-[#334155] text-[#94a3b8]">
                  AC: <strong class="text-[#00d2d3]">{{ note.ac_value }}</strong>
                </span>
                <span class="px-2 py-0.5 rounded bg-[#182234] border border-[#334155] text-[#94a3b8]">
                  跨: <strong class="text-[#f8fafc]">{{ note.span_red }}</strong>
                </span>
                <span class="px-2 py-0.5 rounded bg-[#00d2d3]/20 border border-[#00d2d3]/40 text-[#00d2d3] font-bold">
                  {{ (note.confidence_score * 100).toFixed(1) }}%
                </span>
              </div>
            </div>
          </div>

          <div
            v-else
            class="h-64 flex flex-col items-center justify-center text-[#64748b] text-sm font-mono space-y-2"
          >
            <span>点击左侧「启动离线量化推演」即可生成 5 注方案</span>
          </div>
        </QuantCard>

        <!-- Candidate Pool & Blue Probabilities -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- Red Candidate Pool -->
          <QuantCard title="红球候选胆拖池 (Candidate Pool)">
            <div v-if="result?.candidate_pool" class="space-y-3 font-mono text-xs">
              <div>
                <span class="text-[#ff4757] font-bold mr-2">核心胆码 (Cores):</span>
                <div class="flex items-center space-x-1.5 mt-1.5">
                  <BallBadge
                    v-for="c in result.candidate_pool.cores"
                    :key="c"
                    :num="c"
                    type="red"
                    size="sm"
                  />
                  <span v-if="!result.candidate_pool.cores?.length" class="text-[#64748b]">无强制胆码</span>
                </div>
              </div>
              <div>
                <span class="text-[#94a3b8] font-bold mr-2">托码备选 (Satellites):</span>
                <div class="flex flex-wrap gap-1.5 mt-1.5">
                  <BallBadge
                    v-for="s in result.candidate_pool.satellites"
                    :key="s"
                    :num="s"
                    type="red"
                    size="sm"
                  />
                </div>
              </div>
            </div>
            <div v-else class="text-[#64748b] text-xs font-mono py-4 text-center">暂无候选池数据</div>
          </QuantCard>

          <!-- Blue Probabilities -->
          <QuantCard title="蓝球概率与排序 (Top Blue Ranking)">
            <div v-if="result?.blue_probabilities" class="space-y-2 font-mono text-xs">
              <div
                v-for="b in result.blue_probabilities.slice(0, 5)"
                :key="b.ball"
                class="flex items-center justify-between p-1.5 rounded bg-[#111827] border border-[#1e293b]"
              >
                <div class="flex items-center space-x-2">
                  <span class="text-[#64748b] font-bold w-4">#{{ b.rank }}</span>
                  <BallBadge :num="b.ball" type="blue" size="sm" />
                </div>
                <div class="flex items-center space-x-2">
                  <div class="w-24 bg-[#1e293b] rounded-full h-1.5 overflow-hidden">
                    <div
                      class="bg-[#00d2d3] h-full rounded-full"
                      :style="{ width: `${Math.min(100, b.probability * 300)}%` }"
                    ></div>
                  </div>
                  <span class="text-[#00d2d3] font-bold w-12 text-right">
                    {{ (b.probability * 100).toFixed(1) }}%
                  </span>
                </div>
              </div>
            </div>
            <div v-else class="text-[#64748b] text-xs font-mono py-4 text-center">暂无蓝球概率数据</div>
          </QuantCard>
        </div>

        <!-- Markdown Mathematical Rationale -->
        <QuantCard title="纯量化数学推演决策逻辑 (Quantitative Mathematical Rationale)">
          <div
            v-if="result?.ai_reasoning_md"
            class="prose prose-invert max-w-none text-xs text-[#cbd5e1] font-mono whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto p-2 rounded bg-[#111827] border border-[#1e293b]"
          >
            {{ result.ai_reasoning_md }}
          </div>
          <div v-else class="text-[#64748b] text-xs font-mono py-6 text-center">
            推演完成后将在此处展示数学决策依据与赔率矩阵
          </div>
        </QuantCard>
      </div>
    </div>
  </div>
</template>
