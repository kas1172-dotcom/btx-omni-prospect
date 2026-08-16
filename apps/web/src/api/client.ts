import type { Account, Account360, Alert, MapRecord, OmniResponse, Signal, WorkItem } from '../types/api'

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '')
const request = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(`${apiBase}${path}`, { headers: { 'content-type': 'application/json' }, ...init })
  if (!response.ok) throw new Error((await response.text()) || `Request failed: ${response.status}`)
  return response.json() as Promise<T>
}

export const api = {
  accounts: () => request<{ accounts: Account[] }>('/accounts'),
  account: (id: string) => request<Account360>(`/accounts/${id}`),
  today: () => request<{ priority_intelligence: Signal[]; commercial_alerts: Alert[]; recommended_actions: Array<{ account_id: string; action: string; evidence_ids: string[] }> }>('/today'),
  intelligence: () => request<{ signals: Signal[] }>('/intelligence'),
  map: (industry?: string) => request<{ layers: string[]; records: MapRecord[] }>('/map' + (industry ? `?industry=${encodeURIComponent(industry)}` : '')),
  createAction: (body: { account_id: string; summary: string; evidence_ids: string[]; idempotency_key: string; actor_id: string; priority?: string }) => request<WorkItem>('/actions', { method: 'POST', body: JSON.stringify(body) }),
  transition: (id: string, status: string) => request<WorkItem>(`/actions/${id}/${status}`, { method: 'POST', body: JSON.stringify({ actor_id: 'poc-user' }) }),
  audit: (id: string) => request<{ events: unknown[] }>(`/actions/${id}/audit`),
  preview: (id: string) => request<{ confirmed: boolean; executed: boolean }>(`/actions/${id}/crm-preview`, { method: 'POST' }),
  execute: (id: string) => request<{ executed: boolean }>(`/actions/${id}/crm-execute?confirmed=true`, { method: 'POST' }),
  omni: (account_id: string, question: string) => request<OmniResponse>('/omni', { method: 'POST', body: JSON.stringify({ account_id, question }) }),
}
