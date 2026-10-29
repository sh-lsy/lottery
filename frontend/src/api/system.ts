import client from './client';
import type { SystemHealth } from '../types/api';

export function getHealth(): Promise<SystemHealth> {
  return client.get('/health');
}
