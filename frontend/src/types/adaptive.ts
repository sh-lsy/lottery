export interface AdaptiveStateResponse {
  current_issue?: string | null;
  consecutive_deficit_count: number;
  consecutive_losses?: number | null;
  adaptation_triggered: boolean;
  trigger_threshold: number;
  loss_threshold?: number | null;
  weights: {
    hazard: number;
    markov: number;
    momentum: number;
    [key: string]: number;
  };
  current_weights?: Record<string, number> | null;
  blue_mode: 'CONCENTRATED' | 'DISPERSED' | 'BALANCED' | string;
  current_strategy_mode?: string | null;
  temperature_tau?: number | null;
  sum_range?: number[] | null;
  last_deviation?: Record<string, number> | null;
  active_hyperparams?: Record<string, any> | null;
  last_trigger_issue?: string | null;
  last_trigger_reason?: string | null;
  evolution_version?: number | null;
  updated_at?: string | null;
}

export interface AdaptiveTrajectoryItem {
  id: number;
  issue_no: string;
  trigger_issue?: string | null;
  consecutive_deficit_count: number;
  consecutive_losses?: number | null;
  is_triggered: boolean;
  trigger_event?: string | null;
  trigger_reason?: string | null;
  weight_hazard: number;
  weight_markov: number;
  weight_momentum: number;
  blue_mode: string;
  sum_deviation: number;
  odd_deviation: number;
  cold_deviation: number;
  hot_deviation: number;
  bias_metrics?: Record<string, any> | null;
  action_taken?: string | null;
  reflection_notes?: string | null;
  created_at: string;
}

export interface AdaptiveTrajectoryResponse {
  total_records: number;
  items: AdaptiveTrajectoryItem[];
}
