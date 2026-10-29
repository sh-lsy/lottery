import client from './client';
import type { AdaptiveStateResponse, AdaptiveTrajectoryResponse } from '../types/adaptive';

export function getAdaptiveStatus(): Promise<AdaptiveStateResponse> {
  return client.get('/adaptive/status');
}

export function getAdaptiveTrajectory(limit: number = 20): Promise<AdaptiveTrajectoryResponse> {
  return client.get('/adaptive/trajectory', { params: { limit } });
}

export function resetAdaptive(): Promise<AdaptiveStateResponse> {
  return client.post('/adaptive/reset');
}
