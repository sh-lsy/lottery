import client from './client';
import type {
  PredictionGenerateRequest,
  PredictionGenerateResponse,
  PredictionSaveRequest,
  PredictionSaveResponse,
  PredictionBatchSummary,
  PredictionBatchDetail,
  PredictDashboardResponse,
} from '../types/predict';
import type { PaginatedResponse } from '../types/api';

export function generatePrediction(request: PredictionGenerateRequest): Promise<PredictionGenerateResponse> {
  return client.post('/predict/generate', request);
}

export function savePrediction(request: PredictionSaveRequest): Promise<PredictionSaveResponse> {
  return client.post('/predict/save', request);
}

export interface BatchQueryParams {
  page?: number;
  page_size?: number;
  target_issue?: string;
  strategy_type?: string;
  verify_status?: string;
}

export function listPredictionBatches(params: BatchQueryParams = {}): Promise<PaginatedResponse<PredictionBatchSummary>> {
  return client.get('/predict/batches', { params });
}

export function getPredictionBatch(batchId: number): Promise<PredictionBatchDetail> {
  return client.get(`/predict/batches/${batchId}`);
}

export function getPredictDashboard(): Promise<PredictDashboardResponse> {
  return client.get('/predict/dashboard');
}
