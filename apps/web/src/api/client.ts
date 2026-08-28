import type { Account, Account360, AccountRelationships, Action, ActionHistoryEvent, ActionPriority, ActionStatus, Alert, BtxMapFacility, MapIntelligence, MapRecord, MonitorHealth, OmniContext, OmniResponse, Principal, PublicLocation, Signal, Suggestion } from '../types/api'

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '')
const request = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(`${apiBase}${path}`, { headers: { 'content-type': 'application/json' }, ...init })
  if (!response.ok) throw new Error((await response.text()) || `Request failed: ${response.status}`)
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
const principalToken = () => sessionStorage.getItem('btx-principal-token') ?? 'development-salesperson'
const actionRequest = <T>(path: string, init?: RequestInit) => request<T>(path, { ...init, headers: { 'content-type': 'application/json', 'X-BTX-Principal-Token': principalToken() } })

export const api = {
  accounts: () => request<{ accounts: Account[] }>('/accounts'),
  account: (id: string) => request<Account360>(`/accounts/${id}`),
  relationships: (accountId: string) => request<AccountRelationships>(`/accounts/${accountId}/relationships?depth=2`),
  today: () => request<{ priority_intelligence: Signal[]; commercial_alerts: Alert[]; recommended_actions: Array<{ account_id: string; action: string; evidence_ids: string[] }> }>('/today'),
  intelligence: () => request<{ signals: Signal[] }>('/intelligence'),
  map: (industry?: string) => request<{ layers: string[]; accounts: MapRecord[]; facilities: PublicLocation[]; btx_facilities: BtxMapFacility[]; intelligence: MapIntelligence[] }>('/map' + (industry ? `?industry=${encodeURIComponent(industry)}` : '')),
  actions: () => actionRequest<{ items: Action[]; suggestions: Suggestion[]; principal: Principal; persistence: string; warning: string }>('/actions'),
  createAction: (body: { account_id: string; title: string; description?: string; owner_id?: string; priority: ActionPriority; due_date?: string; evidence_ids?: string[]; approval_required?: boolean; idempotency_key?: string }) => actionRequest<Action>('/actions', { method: 'POST', body: JSON.stringify(body) }),
  editAction: (id: string, body: Partial<Pick<Action, 'title' | 'description' | 'owner_id' | 'priority' | 'due_date'>>) => actionRequest<Action>(`/actions/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  transition: (id: string, status: ActionStatus) => actionRequest<Action>(`/actions/${id}/status`, { method: 'POST', body: JSON.stringify({ status }) }),
  approve: (id: string, decision: 'APPROVED' | 'REJECTED') => actionRequest<Action>(`/actions/${id}/approval`, { method: 'POST', body: JSON.stringify({ decision }) }),
  convertSuggestion: (id: string) => actionRequest<Action>(`/actions/suggestions/${id}/convert`, { method: 'POST', body: '{}' }),
  dismissSuggestion: (id: string) => actionRequest<void>(`/actions/suggestions/${id}/dismiss`, { method: 'POST' }),
  history: (id: string) => actionRequest<{ events: ActionHistoryEvent[] }>(`/actions/${id}/history`),
  preview: (id: string) => actionRequest<{ confirmed: boolean; executed: boolean }>(`/actions/${id}/crm-preview`, { method: 'POST' }),
  execute: (id: string) => actionRequest<{ executed: boolean }>(`/actions/${id}/crm-execute?confirmed=true`, { method: 'POST' }),
  omni: (account_id: string | undefined, question: string, context?: OmniContext) => actionRequest<OmniResponse>('/omni', { method: 'POST', body: JSON.stringify({ account_id, question, context }) }),
  monitor: () => request<MonitorHealth>('/monitor/health'),
}
