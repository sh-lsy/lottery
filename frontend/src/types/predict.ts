export interface PredictionNoteItem {
  note_index: number;
  reds: number[];
  blue: number;
  confidence_score: number;
  rationale?: string | null;
  sum_red?: number | null;
  ac_value?: number | null;
  odd_count?: number | null;
  span_red?: number | null;
  metrics?: Record<string, any> | null;
}

export interface CandidatePoolSummary {
  cores: number[];
  satellites: number[];
}

export interface BlueProbabilityItem {
  ball: number;
  probability: number;
  rank: number;
}

export interface PredictionGenerateRequest {
  target_issue?: string | null;
  strategy_type?: string;
  strategy?: string | null;
  ac_min?: number;
  sum_min?: number;
  sum_max?: number;
  odd_counts?: number[];
  max_consecutive_pairs?: number;
  span_min?: number;
  span_max?: number;
  blue_mode?: string | null;
  adaptive_enabled?: boolean;
  save_to_db?: boolean;
  custom_filters?: Record<string, any> | null;
}

export interface PredictionGenerateResponse {
  target_issue: string;
  strategy_type: string;
  model_name: string;
  total_notes: number;
  notes: PredictionNoteItem[];
  ai_reasoning_md: string;
  filter_params: Record<string, any>;
  candidate_pool: CandidatePoolSummary;
  blue_probabilities?: BlueProbabilityItem[] | null;
  break_even_matrix?: Record<string, any> | null;
  batch_id?: number | null;
}

export interface PredictionSaveRequest {
  target_issue: string;
  strategy_type?: string;
  model_name?: string;
  filter_params?: Record<string, any> | null;
  ai_reasoning_md?: string | null;
  notes: PredictionNoteItem[];
  virtual_cost?: number;
}

export interface PredictionSaveResponse {
  batch_id: number;
  target_issue: string;
  total_notes: number;
  message: string;
}

export interface PredictionBatchSummary {
  id: number;
  target_issue: string;
  strategy_type: string;
  model_name?: string | null;
  total_notes: number;
  verify_status: string;
  best_prize_level: number;
  virtual_cost: number;
  virtual_reward: number;
  net_profit: number;
  roi: number;
  created_at: string;
  verified_at?: string | null;
}

export interface PredictionItemDetail {
  id: number;
  note_index: number;
  reds: number[];
  blue: number;
  confidence_score: number;
  rationale?: string | null;
  is_verified: boolean;
  hit_red_count: number;
  hit_red_numbers: number[];
  hit_red_str?: string | null;
  hit_blue: boolean;
  prize_level: number;
  prize_amount: number;
}

export interface PredictionBatchDetail extends PredictionBatchSummary {
  filter_params_json?: string | null;
  ai_reasoning_md?: string | null;
  post_reflection_md?: string | null;
  items: PredictionItemDetail[];
  actual_draw?: {
    issue_no: string;
    draw_date: string;
    weekday: number;
    reds: number[];
    blue: number;
    red_seq_str?: string;
    first_prize_num?: number;
    first_prize_amount?: number;
    second_prize_num?: number;
    second_prize_amount?: number;
  } | null;
}

export interface PredictDashboardResponse {
  total_batches: number;
  total_notes: number;
  total_investment: number;
  total_returns: number;
  net_profit: number;
  simulated_roi: number;
  break_even_batches: number;
  break_even_rate: number;
  blue_hit_batches: number;
  blue_hit_rate: number;
  prize_distribution: Record<number, number>;
  strategy_breakdown?: Record<string, any> | null;
}
