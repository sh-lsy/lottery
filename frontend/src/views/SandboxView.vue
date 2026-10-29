<script setup lang="ts">
import { ref, computed } from 'vue';
import { ElMessage } from 'element-plus';
import { collideSandbox } from '../api/backtest';
import type { SandboxCollisionResponse } from '../types/sandbox';
import BallBadge from '../components/common/BallBadge.vue';
import MetricCard from '../components/common/MetricCard.vue';
import QuantCard from '../components/common/QuantCard.vue';

// Selected balls
const selectedReds = ref<number[]>([2, 7, 14, 19, 24, 31]);
const selectedBlue = ref<number>(8);

const colliding = ref(false);
const collisionResult = ref<SandboxCollisionResponse | null>(null);

// Number grids
const redBalls = Array.from({ length: 33 }, (_, i) => i + 1);
const blueBalls = Array.from({ length: 16 }, (_, i) => i + 1);

function toggleRed(num: number) {
  const idx = selectedReds.value.indexOf(num);
  if (idx !== -1) {
    selectedReds.value.splice(idx, 1);
  } else {
    if (selectedReds.value.length >= 6) {
      ElMessage.warning('已选满 6 个红球，请先取消一个后再选择');
      return;
    }
    selectedReds.value.push(num);
    selectedReds.value.sort((a, b) => a - b);
  }
}

function selectBlueBall(num: number) {
  selectedBlue.value = num;
}

function randomPickReds() {
  const pool = [...redBalls];
  const picked: number[] = [];
  for (let i = 0; i < 6; i++) {
    const idx = Math.floor(Math.random() * pool.length);
    picked.push(pool[idx]);
    pool.splice(idx, 1);
  }
  selectedReds.value = picked.sort((a, b) => a - b);
}

function randomPickBlue() {
  selectedBlue.value = Math.floor(Math.random() * 16) + 1;
}

function clearSelection() {
  selectedReds.value = [];
}

// Characteristic calculations
const currentSum = computed(() => {
  return selectedReds.value.reduce((acc, v) => acc + v, 0);
});

const currentSpan = computed(() => {
  if (selectedReds.value.length < 2) return 0;
  return selectedReds.value[selectedReds.value.length - 1] - selectedReds.value[0];
});

const currentOddCount = computed(() => {
  return selectedReds.value.filter((r) => r % 2 === 1).length;
});

async function handleCollision() {
  if (selectedReds.value.length !== 6) {
    ElMessage.error('请选择恰好 6 个红球');
    return;
  }
  if (!selectedBlue.value) {
    ElMessage.error('请选择 1 个蓝球');
    return;
  }

  colliding.value = true;
  try {
    const res = await collideSandbox({
      reds: selectedReds.value,
      blue: selectedBlue.value,
    });
    collisionResult.value = res;
    ElMessage.success(`历史碰撞完成！已穿透比对 ${res.total_draws_analyzed} 期历史数据`);
  } catch {
    ElMessage.error('碰撞比对失败，请检查后端状态');
  } finally {
    colliding.value = false;
  }
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

// Auto-run once on load
handleCollision();
</script>

<template>
  <div class="space-y-6">
    <!-- Interactive Ball Picker -->
    <QuantCard title="号码组合选择器 (Interactive Ball Selector)">
      <template #action>
        <div class="flex items-center space-x-2 font-mono text-xs">
          <el-button size="small" @click="randomPickReds" class="!bg-[#111827] !border-[#334155] !text-[#f8fafc]">
            🎲 机选 6 红
          </el-button>
          <el-button size="small" @click="randomPickBlue" class="!bg-[#111827] !border-[#334155] !text-[#00d2d3]">
            🎲 机选 1 蓝
          </el-button>
          <el-button size="small" @click="clearSelection" class="!bg-[#111827] !border-[#334155] !text-[#94a3b8]">
            清空
          </el-button>
        </div>
      </template>

      <div class="space-y-4">
        <!-- Red Balls Grid -->
        <div>
          <div class="flex items-center justify-between text-xs text-[#94a3b8] mb-2 font-mono">
            <span>红球选择 (已选 {{ selectedReds.length }}/6):</span>
            <span class="text-[#ff4757] font-bold">Primary Sequence (01-33)</span>
          </div>
          <div class="grid grid-cols-11 md:grid-cols-17 gap-2">
            <button
              v-for="num in redBalls"
              :key="num"
              @click="toggleRed(num)"
              class="h-8 rounded-md font-mono text-xs font-bold transition-all flex items-center justify-center border"
              :class="[
                selectedReds.includes(num)
                  ? 'bg-[#ff4757] text-white border-[#ff4757] shadow-[0_0_8px_rgba(255,71,87,0.7)] scale-105'
                  : 'bg-[#111827] text-[#94a3b8] border-[#334155] hover:border-[#64748b] hover:text-white'
              ]"
            >
              {{ num < 10 ? `0${num}` : num }}
            </button>
          </div>
        </div>

        <!-- Blue Balls Grid -->
        <div>
          <div class="flex items-center justify-between text-xs text-[#94a3b8] mb-2 font-mono">
            <span>蓝球选择 (已选 {{ selectedBlue ? 1 : 0 }}/1):</span>
            <span class="text-[#00d2d3] font-bold">Secondary Scalar (01-16)</span>
          </div>
          <div class="grid grid-cols-8 md:grid-cols-16 gap-2">
            <button
              v-for="num in blueBalls"
              :key="num"
              @click="selectBlueBall(num)"
              class="h-8 rounded-md font-mono text-xs font-bold transition-all flex items-center justify-center border"
              :class="[
                selectedBlue === num
                  ? 'bg-[#00d2d3] text-[#0b0f19] border-[#00d2d3] shadow-[0_0_8px_rgba(0,210,211,0.7)] scale-105'
                  : 'bg-[#111827] text-[#94a3b8] border-[#334155] hover:border-[#64748b] hover:text-white'
              ]"
            >
              {{ num < 10 ? `0${num}` : num }}
            </button>
          </div>
        </div>

        <!-- Selection Summary Bar & Action -->
        <div class="p-3.5 bg-[#111827] border border-[#334155] rounded-lg flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div class="flex items-center space-x-3">
            <span class="text-xs text-[#94a3b8] font-mono">当前待验组合:</span>
            <div class="flex items-center space-x-1.5">
              <BallBadge
                v-for="r in selectedReds"
                :key="r"
                :num="r"
                type="red"
                size="md"
              />
              <span v-if="selectedReds.length === 0" class="text-xs text-[#64748b] font-mono">请点选红球</span>
              <span class="text-[#64748b] font-bold">+</span>
              <BallBadge
                v-if="selectedBlue"
                :num="selectedBlue"
                type="blue"
                size="md"
              />
              <span v-else class="text-xs text-[#64748b] font-mono">请点选蓝球</span>
            </div>
          </div>

          <!-- Realtime Features -->
          <div class="flex items-center space-x-3 text-xs font-mono text-[#94a3b8]">
            <span>和值: <strong class="text-white">{{ currentSum }}</strong></span>
            <span>跨度: <strong class="text-white">{{ currentSpan }}</strong></span>
            <span>奇偶: <strong class="text-white">{{ currentOddCount }}:{{ 6 - currentOddCount }}</strong></span>
          </div>

          <!-- Collision Trigger Button -->
          <el-button
            type="primary"
            size="default"
            class="!bg-gradient-to-r !from-[#ff4757] !to-[#00d2d3] !border-none !text-white !font-bold !h-10 !px-6 shadow-lg tracking-wider"
            :loading="colliding"
            :disabled="selectedReds.length !== 6 || !selectedBlue"
            @click="handleCollision"
          >
            🚀 执行全量 3500+ 期历史碰撞 (Sub-15ms)
          </el-button>
        </div>
      </div>
    </QuantCard>

    <!-- Collision Results Section -->
    <div v-if="collisionResult" class="space-y-6">
      <!-- 4 KPI Metrics -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard
          label="全历史最高命中奖项"
          :value="collisionResult.highest_prize_name || '未中奖'"
          :sub-value="`最高级别: ${collisionResult.highest_prize_level ? collisionResult.highest_prize_level + '等奖' : '无'}`"
          :color="collisionResult.highest_prize_level > 0 && collisionResult.highest_prize_level <= 3 ? 'rose' : 'cyan'"
        />
        <MetricCard
          label="全历史累计奖金回报"
          :value="formatAmount(collisionResult.total_historical_payout)"
          :sub-value="`碰撞期数: ${collisionResult.total_draws_analyzed} 期`"
          color="emerald"
        />
        <MetricCard
          label="假设全买入成本"
          :value="formatAmount(collisionResult.hypothetical_cost)"
          sub-value="每期 2 元"
          color="default"
        />
        <MetricCard
          label="全历史模拟 ROI"
          :value="`${(collisionResult.hypothetical_roi * 100).toFixed(1)}%`"
          :sub-value="`净收益: ${formatAmount(collisionResult.hypothetical_net_profit)}`"
          :color="collisionResult.hypothetical_roi >= 0 ? 'emerald' : 'rose'"
        />
      </div>

      <!-- Charts & Quantiles Grid -->
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <!-- Prize Counts Distribution (5 cols) -->
        <div class="lg:col-span-5 space-y-4">
          <QuantCard title="各等级中奖频次统计 (Prize Distribution)">
            <div class="space-y-3 font-mono text-xs">
              <div
                v-for="(count, prizeKey) in collisionResult.prize_counts"
                :key="prizeKey"
                class="flex items-center justify-between p-2 rounded bg-[#111827] border border-[#1e293b]"
              >
                <span class="text-[#94a3b8] font-bold">{{ prizeKey }}</span>
                <span class="text-white font-bold">{{ count }} 次</span>
              </div>
            </div>
          </QuantCard>

          <!-- Quantile Gauge / Percentiles -->
          <QuantCard title="数学特征历史分位数 (Quantile Percentiles)">
            <div v-if="collisionResult.quantile_metrics" class="space-y-4 font-mono text-xs">
              <div
                v-for="qm in collisionResult.quantile_metrics"
                :key="qm.metric_name"
                class="p-2.5 rounded bg-[#111827] border border-[#1e293b] space-y-1"
              >
                <div class="flex items-center justify-between">
                  <span class="text-[#94a3b8]">{{ qm.metric_name }}</span>
                  <span class="text-[#00d2d3] font-bold">{{ qm.ticket_value }} ({{ qm.percentile }}% 分位)</span>
                </div>
                <div class="w-full bg-[#1e293b] rounded-full h-2 overflow-hidden">
                  <div
                    class="bg-gradient-to-r from-[#00d2d3] to-[#3b82f6] h-full rounded-full"
                    :style="{ width: `${qm.percentile}%` }"
                  ></div>
                </div>
                <div class="flex justify-between text-[10px] text-[#64748b]">
                  <span>历史均值: {{ qm.historical_mean }}</span>
                  <span>区间: [{{ qm.historical_min }}, {{ qm.historical_max }}]</span>
                </div>
              </div>
            </div>
          </QuantCard>
        </div>

        <!-- Historical Matches Table (7 cols) -->
        <div class="lg:col-span-7">
          <QuantCard title="高奖级历史碰撞命中期次记录 (Top Matches)">
            <div class="overflow-x-auto rounded border border-[#1e293b]">
              <table class="w-full text-left text-xs font-mono border-collapse">
                <thead class="bg-[#111827] text-[#94a3b8] border-b border-[#334155]">
                  <tr>
                    <th class="py-2.5 px-3">期号</th>
                    <th class="py-2.5 px-3">开奖日期</th>
                    <th class="py-2.5 px-3">命中间隔</th>
                    <th class="py-2.5 px-3">中奖等级</th>
                    <th class="py-2.5 px-3 text-right">奖金</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-[#1e293b]">
                  <tr
                    v-for="m in collisionResult.top_matches"
                    :key="m.issue_no"
                    class="hover:bg-[#1e293b]/50 transition-colors"
                  >
                    <td class="py-2 px-3 font-bold text-white">{{ m.issue_no }}</td>
                    <td class="py-2 px-3 text-[#94a3b8]">{{ m.draw_date }}</td>
                    <td class="py-2 px-3">
                      <span class="text-[#ff4757] font-bold">{{ m.hit_red_count }} 红</span> +
                      <span :class="m.hit_blue ? 'text-[#00d2d3] font-bold' : 'text-[#64748b]'">
                        {{ m.hit_blue ? '1 蓝' : '0 蓝' }}
                      </span>
                    </td>
                    <td class="py-2 px-3">
                      <span
                        class="px-2 py-0.5 rounded text-[11px] font-bold"
                        :class="[
                          m.prize_level <= 3 ? 'bg-[#ff4757]/20 text-[#ff4757] border border-[#ff4757]/40' :
                          m.prize_level <= 5 ? 'bg-[#10b981]/20 text-[#10b981] border border-[#10b981]/40' :
                          'bg-[#00d2d3]/20 text-[#00d2d3] border border-[#00d2d3]/40'
                        ]"
                      >
                        {{ m.prize_level }}等奖
                      </span>
                    </td>
                    <td class="py-2 px-3 text-right font-bold text-[#f59e0b]">
                      ¥{{ m.prize_amount.toLocaleString() }}
                    </td>
                  </tr>
                  <tr v-if="!collisionResult.top_matches || collisionResult.top_matches.length === 0">
                    <td colspan="5" class="text-center py-6 text-[#64748b]">该组合在历史开奖中未中出较高奖级</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </QuantCard>
        </div>
      </div>
    </div>
  </div>
</template>
