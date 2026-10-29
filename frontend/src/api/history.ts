import client from './client';
import type {
  DrawRecordItem,
  IndicatorDistributionResponse,
  OmissionTrendResponse,
  SyncResponseData,
} from '../types/history';
import type { PaginatedResponse } from '../types/api';

export interface DrawQueryParams {
  page?: number;
  page_size?: number;
  start_issue?: string;
  end_issue?: string;
  sort_order?: 'asc' | 'desc';
  search_ball?: number;
}

export function getDrawHistory(params: DrawQueryParams = {}): Promise<PaginatedResponse<DrawRecordItem>> {
  return client.get('/history/draws', { params });
}

export function getLatestDraw(): Promise<DrawRecordItem> {
  return client.get('/history/latest');
}

export function getOmissionTrends(limit: number = 30): Promise<OmissionTrendResponse> {
  return client.get('/history/omissions', { params: { limit } });
}

export function getDistributions(recent_n: number = 100): Promise<IndicatorDistributionResponse> {
  return client.get('/history/distributions', { params: { recent_n } });
}

export function syncHistory(force: boolean = false): Promise<SyncResponseData> {
  return client.post('/history/sync', { force, auto_verify: true });
}
