export interface SandboxCollisionRequest {
  reds: number[];
  blue: number;
}

export interface HistoricalMatchItem {
  issue_no: string;
  draw_date: string;
  actual_reds: number[];
  actual_blue: number;
  hit_red_count: number;
  hit_reds: number[];
  hit_blue: boolean;
  prize_level: number;
  prize_amount: number;
}

export interface QuantileMetricItem {
  metric_name: string;
  ticket_value: number;
  historical_mean: number;
  historical_min: number;
  historical_max: number;
  percentile: number;
  evaluation: string;
}

export interface SandboxCollisionResponse {
  ticket_reds: number[];
  ticket_blue: number;
  input_reds?: number[] | null;
  input_blue?: number | null;
  total_draws_analyzed: number;
  total_draws_scanned?: number | null;
  highest_prize_level: number;
  highest_prize_name: string;
  best_prize_level?: number | null;
  best_prize_name?: string | null;
  best_prize_issue?: string | null;
  total_historical_payout: number;
  total_payout?: number | null;
  hypothetical_cost: number;
  total_cost?: number | null;
  hypothetical_net_profit: number;
  net_profit?: number | null;
  hypothetical_roi: number;
  simulated_roi?: number | null;
  prize_counts: Record<string, number>;
  prize_distribution?: Record<number, number> | null;
  features?: Record<string, any> | null;
  percentiles?: Record<string, number> | null;
  quantile_metrics?: QuantileMetricItem[] | null;
  top_matches?: HistoricalMatchItem[] | null;
}
