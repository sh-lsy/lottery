export interface FeatureMetricsItem {
  issue_no: string;
  sum_red: number;
  span_red: number;
  ac_value: number;
  odd_count: number;
  prime_count: number;
  zone1_count: number;
  zone2_count: number;
  zone3_count: number;
  consecutive_groups: number;
  repeat_prev_red: number;
  missing_sum_red: number;
  missing_blue: number;
}

export interface DrawRecordItem {
  id: number;
  issue_no: string;
  draw_date: string;
  weekday: number;
  reds: number[];
  blue: number;
  red_seq_str?: string | null;
  sales_amount: number;
  pool_amount: number;
  first_prize_num: number;
  first_prize_amount: number;
  second_prize_num: number;
  second_prize_amount: number;
  metrics?: FeatureMetricsItem | null;
  sum_red?: number | null;
  ac_value?: number | null;
  odd_count?: number | null;
  prime_count?: number | null;
  zones?: number[] | null;
}

export interface OmissionTrendItem {
  issue_no: string;
  draw_date: string;
  red_omissions: Record<string, number>;
  blue_omissions: Record<string, number>;
  drawn_reds: number[];
  drawn_blue: number;
}

export interface ColdWarmHotSummary {
  hot_reds: number[];
  warm_reds: number[];
  cold_reds: number[];
  hot_blues: number[];
  warm_blues: number[];
  cold_blues: number[];
}

export interface OmissionTrendResponse {
  issues: string[];
  timeline: OmissionTrendItem[];
  current_red_omissions: Record<string, number>;
  current_blue_omissions: Record<string, number>;
  cold_warm_hot: ColdWarmHotSummary;
  top3_hot_reds: number[];
  top3_cold_reds: number[];
  top3_hot_blues: number[];
  top3_cold_blues: number[];
}

export interface IndicatorDistributionResponse {
  sample_size: number;
  sum_distribution: Record<string, number>;
  ac_distribution: Record<number, number>;
  odd_even_distribution: Record<string, number>;
  span_distribution: Record<string, number>;
  zone_distribution: Record<string, number>;
}

export interface SyncResponseData {
  success: boolean;
  affected_draws: number;
  new_draws: number;
  total_draws_in_db: number;
  computed_features: number;
  new_features: number;
  verified_batches: number;
  earliest_issue: string | null;
  latest_issue: string | null;
  message: string;
}
