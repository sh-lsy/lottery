import client from './client';
import type { SandboxCollisionRequest, SandboxCollisionResponse } from '../types/sandbox';

export function collideSandbox(request: SandboxCollisionRequest): Promise<SandboxCollisionResponse> {
  return client.post('/backtest/sandbox/collision', request);
}

export function verifyIssue(issueNo: string, force: boolean = false): Promise<any> {
  return client.post(`/backtest/verify/${issueNo}`, null, { params: { force } });
}
