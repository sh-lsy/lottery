export interface ApiResponse<T = any> {
  code: number;
  message: string;
  data?: T;
}

export interface PaginatedResponse<T = any> {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  items: T[];
}

export interface SystemHealth {
  status: string;
  engine: string;
  version: string;
  database: {
    dialect: string;
    total_draws: number;
    latest_issue: string | null;
    total_prediction_batches: number;
  };
}
