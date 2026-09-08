import type { Account, Account360, AccountRelationships, Action, ActionHistoryEvent, ActionPriority, ActionStatus, Alert, BtxMapFacility, CommandCenter, CommunicationDraft, CommunicationHistoryEvent, FederalProcurement, HostedSession, MapIntelligence, MapRecord, MonitorHealth, OmniContext, OmniResponse, Principal, PublicLocation, Signal, Suggestion, WorkspaceSettings } from '../types/api'
import type { RankedRelationships, RelationshipQuery } from '../types/relationships'
import type { OmniMemory, OmniMemoryInput } from '../types/memory'
import type { PendingMapAccount } from '../types/api'
import type { SuggestionFeedback, SuggestionFeedbackInput } from '../types/api'
import type { SuggestionFeedbackHistory } from '../types/api'
import type { MarketOverview, MarketDetail, MarketTransformation } from '../types/markets'
import type { WorkbookPage } from '../features/accounts/WorkbookFields'
import type { CrmProposal, CrmDecision, CrmAttempt, CrmHistory } from '../types/crm'
import type { AiUsageSummary } from '../features/settings/AiUsage'
import type { OmniRun } from '../types/omniRun'
import type { PublicSourceEvidence } from '../types/publicEvidence'

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '')
const request = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(`${apiBase}${path}`, { credentials: 'include', headers: { 'content-type': 'application/json' }, ...init })
  if (!response.ok) throw new Error((await response.text()) || `Request failed: ${response.status}`)
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
let csrfToken: string | undefined
const developmentPrincipalHeaders: Record<string, string> = import.meta.env.DEV
  ? { 'X-BTX-Principal-Token': sessionStorage.getItem('btx-principal-token') ?? 'development-salesperson' }
  : {}
const actionRequest = <T>(path: string, init?: RequestInit) => request<T>(path, { ...init, headers: { 'content-type': 'application/json', ...developmentPrincipalHeaders, ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}) } })

export const api = {
  omniRun: (id: string, signal?: AbortSignal) => actionRequest<OmniRun>(`/omni/runs/${encodeURIComponent(id)}`, { signal }),
  aiUsage: (signal?: AbortSignal) => actionRequest<AiUsageSummary>('/settings/ai-usage', { signal }),
  session: async () => { const value = await request<HostedSession>('/session'); csrfToken = value.csrf_token; return value },
  signIn: async (access_code: string) => { const value = await request<HostedSession>('/session/sign-in', { method: 'POST', body: JSON.stringify({ access_code }) }); csrfToken = value.csrf_token; return value },
  signOut: async () => { const value = await actionRequest<{ authenticated: false }>('/session/sign-out', { method: 'POST' }); csrfToken = undefined; return value },
  accounts: (signal?: AbortSignal) => request<{ accounts: Account[] }>('/accounts', { signal }),
  workbookFields: (accountId: string, offset: number, signal?: AbortSignal) => actionRequest<WorkbookPage>(`/accounts/${encodeURIComponent(accountId)}/workbook-fields?offset=${offset}`, { signal }),
  account: (id: string, signal?: AbortSignal) => request<Account360>(`/accounts/${encodeURIComponent(id)}`, { signal }),
  relationships: (accountId: string) => request<AccountRelationships>(`/accounts/${accountId}/relationships?depth=2`),
  rankedRelationships: (body: RelationshipQuery, signal?: AbortSignal) => actionRequest<RankedRelationships>('/relationships/query', { method: 'POST', body: JSON.stringify(body), signal }),
  commercialEvidence: (accountId: string, recordId: string, signal?: AbortSignal) => actionRequest<{ account_id: string; revision: string; as_of: string; kind: string; truth_class: string; record: Record<string, unknown> }>(`/accounts/${encodeURIComponent(accountId)}/commercial/evidence?record_id=${encodeURIComponent(recordId)}`, { signal }),
  commercialDecisions: (accountId: string, signal?: AbortSignal) => actionRequest<CommercialDecisions>(`/accounts/${encodeURIComponent(accountId)}/commercial/decisions`, { signal }),
  commercialRecords: (accountId: string, collection: string, offset: number, signal?: AbortSignal) => actionRequest<{ account_id: string; revision: string; as_of?: string; reference?: Record<string, unknown>; records?: Record<string, unknown>[]; record_key?: string; total?: number; next_offset?: number | null }>(`/accounts/${encodeURIComponent(accountId)}/commercial/${encodeURIComponent(collection)}?offset=${offset}&limit=10`, { signal }),
  followupPreview: (accountId: string, actionId: string, signal?: AbortSignal) => actionRequest<FollowupPreview>(`/accounts/${encodeURIComponent(accountId)}/commercial/follow-ups/${encodeURIComponent(actionId)}/preview`, { method: 'POST', signal }),
  confirmFollowup: (accountId: string, actionId: string, previewToken: string) => actionRequest<Action>(`/accounts/${encodeURIComponent(accountId)}/commercial/follow-ups/${encodeURIComponent(actionId)}/confirm`, { method: 'POST', body: JSON.stringify({ preview_token: previewToken }) }),
  today: (signal?: AbortSignal) => request<{ priority_intelligence: Signal[]; commercial_alerts: Alert[]; recommended_actions: Array<{ account_id: string; action: string; evidence_ids: string[] }>; command_center: CommandCenter }>('/today', { signal }),
  intelligence: (signal?: AbortSignal) => request<{ signals: Signal[] }>('/intelligence', { signal }),
  markets: (kind: MarketTransformation, average: boolean, signal?: AbortSignal) => actionRequest<MarketOverview>(`/markets?kind=${kind}&moving_average=${average}`, { signal }),
  marketSeries: (id: string, kind: MarketTransformation, average: boolean, signal?: AbortSignal) => actionRequest<MarketDetail>(`/markets/${encodeURIComponent(id)}?kind=${kind}&moving_average=${average}`, { signal }),
  intelligenceEvidence: (eventId: string, signal?: AbortSignal) => request<PublicSourceEvidence>(`/intelligence/${encodeURIComponent(eventId)}/evidence`, { signal }),
  federalProcurement: (params = '') => request<FederalProcurement>(`/federal-procurement${params}`),
  map: (industry?: string, signal?: AbortSignal) => request<{ layers: string[]; accounts: MapRecord[]; pending_accounts?: PendingMapAccount[]; facilities: PublicLocation[]; btx_facilities: BtxMapFacility[]; intelligence: MapIntelligence[] }>('/map' + (industry ? `?industry=${encodeURIComponent(industry)}` : ''), { signal }),
  actions: (signal?: AbortSignal) => actionRequest<{ items: Action[]; suggestions: Suggestion[]; principal: Principal; persistence: string; warning: string }>('/actions', { signal }),
  createAction: (body: { account_id: string; title: string; description?: string; owner_id?: string; priority: ActionPriority; due_date?: string; evidence_ids?: string[]; context_referents?: Array<[string, string]>; approval_required?: boolean; idempotency_key?: string }) => actionRequest<Action>('/actions', { method: 'POST', body: JSON.stringify(body) }),
  editAction: (id: string, body: Partial<Pick<Action, 'title' | 'description' | 'owner_id' | 'priority' | 'due_date'>> & { expected_version?: number }) => actionRequest<Action>(`/actions/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  transition: (id: string, status: ActionStatus, expected_version?: number) => actionRequest<Action>(`/actions/${id}/status`, { method: 'POST', body: JSON.stringify({ status, expected_version }) }),
  approve: (id: string, decision: 'APPROVED' | 'REJECTED', expected_version?: number) => actionRequest<Action>(`/actions/${id}/approval`, { method: 'POST', body: JSON.stringify({ decision, expected_version }) }),
  convertSuggestion: (id: string, expected_revision: string) => actionRequest<Action>(`/actions/suggestions/${id}/convert`, { method: 'POST', body: JSON.stringify({ expected_revision }) }),
  dismissSuggestion: (id: string, expected_revision: string) => actionRequest<void>(`/actions/suggestions/${id}/dismiss`, { method: 'POST', body: JSON.stringify({ expected_revision }) }),
  suggestionFeedback: (id: string, body: SuggestionFeedbackInput) => actionRequest<{ receipt_id: string; current: SuggestionFeedback; external_write: false; canonical_scores_changed: false; work_status_changed: false }>(`/actions/suggestions/${encodeURIComponent(id)}/feedback`, { method: 'POST', body: JSON.stringify(body) }),
  suggestionFeedbackHistory: (offset = 0, signal?: AbortSignal) => actionRequest<SuggestionFeedbackHistory>(`/actions/suggestion-feedback/history?offset=${offset}`, { signal }),
  undoSuggestionFeedbackReceipt: (id: string, key: string) => actionRequest<{ receipt_id: string; state: string; scope: string; external_write: false }>(`/actions/suggestion-feedback/${encodeURIComponent(id)}/undo`, { method: 'POST', body: JSON.stringify({ idempotency_key: key }) }),
  history: (id: string) => actionRequest<{ events: ActionHistoryEvent[] }>(`/actions/${id}/history`),
  crmHistory: (id: string, signal?: AbortSignal) => actionRequest<CrmHistory>(`/actions/${encodeURIComponent(id)}/crm-proposals`, { signal }),
  crmPreview: (id: string, expected_version: number) => actionRequest<CrmProposal>(`/actions/${encodeURIComponent(id)}/crm-preview`, { method: 'POST', body: JSON.stringify({ expected_version }) }),
  crmDecision: (id: string, body: { proposal_id: string; decision: 'APPROVED' | 'REJECTED'; expected_decision_id: string | null }) => actionRequest<CrmDecision>(`/actions/${encodeURIComponent(id)}/crm-proposal-decision`, { method: 'POST', body: JSON.stringify(body) }),
  crmExecuteSample: (id: string, body: { proposal_id: string; expected_decision_id: string; idempotency_key: string }) => actionRequest<CrmAttempt>(`/actions/${encodeURIComponent(id)}/crm-execute?confirmed=true`, { method: 'POST', body: JSON.stringify(body) }),
  communications: (signal?: AbortSignal) => actionRequest<{ items: CommunicationDraft[]; principal: Principal; delivery: { state: string; label: string } }>('/communications', { signal }),
  createCommunication: (body: { account_id: string; subject: string; body: string; recipients?: string[]; trigger?: string; evidence_ids?: string[]; idempotency_key?: string }) => actionRequest<CommunicationDraft>('/communications', { method: 'POST', body: JSON.stringify(body) }),
  editCommunication: (id: string, body: Partial<Pick<CommunicationDraft, 'subject' | 'body' | 'recipients'>> & { expected_version: number }) => actionRequest<CommunicationDraft>(`/communications/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  assistCommunication: (id: string, instruction: string, expected_version: number) => actionRequest<{ draft: CommunicationDraft; proposal: { subject: string; body: string; evidence_ids: string[] }; provider_status: string; assisted: boolean; message: string }>(`/communications/${id}/assist`, { method: 'POST', body: JSON.stringify({ instruction, expected_version }) }),
  assistNewCommunication: (body: { account_id: string; instruction: string; subject?: string; body?: string; evidence_ids?: string[] }) => actionRequest<{ proposal: { subject: string; body: string; evidence_ids: string[] }; provider_status: string; assisted: boolean; message: string }>('/communications/assist', { method: 'POST', body: JSON.stringify(body) }),
  approveCommunication: (id: string, decision: 'APPROVED' | 'REJECTED', expected_version: number) => actionRequest<CommunicationDraft>(`/communications/${id}/approval`, { method: 'POST', body: JSON.stringify({ decision, expected_version }) }),
  previewCommunication: (id: string) => actionRequest<{ available: boolean; provider: string; recipient_count: number; message: string }>(`/communications/${id}/preview`, { method: 'POST' }),
  sendCommunication: (id: string, key: string, expectedVersion: number) => actionRequest<CommunicationDraft>(`/communications/${id}/send?confirmed=true&idempotency_key=${encodeURIComponent(key)}&expected_version=${expectedVersion}`, { method: 'POST' }),
  communicationHistory: (id: string, signal?: AbortSignal) => actionRequest<{ events: CommunicationHistoryEvent[] }>(`/communications/${id}/history`, { signal }),
  settings: (signal?: AbortSignal) => actionRequest<WorkspaceSettings>('/settings', { signal }),
  updatePreferences: (body: Partial<WorkspaceSettings['preferences']>) => actionRequest<WorkspaceSettings['preferences']>('/settings/preferences', { method: 'PATCH', body: JSON.stringify(body) }),
  omni: (account_id: string | undefined, question: string, context?: OmniContext) => actionRequest<OmniResponse>('/omni', { method: 'POST', body: JSON.stringify({ account_id, question, context }) }),
  memories: (signal?: AbortSignal) => actionRequest<{ items: OmniMemory[]; authority: string; scope: string }>('/omni/memories', { signal }),
  createMemory: (body: OmniMemoryInput & { idempotency_key: string }) => actionRequest<OmniMemory>('/omni/memories', { method: 'POST', body: JSON.stringify(body) }),
  editMemory: (id: string, body: OmniMemoryInput & { expected_version: number }) => actionRequest<OmniMemory>(`/omni/memories/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteMemory: (id: string, expected_version: number) => actionRequest<{ deleted: boolean }>(`/omni/memories/${encodeURIComponent(id)}/delete`, { method: 'POST', body: JSON.stringify({ expected_version }) }),
  monitor: (signal?: AbortSignal) => request<MonitorHealth>('/monitor/health', { signal }),
}
import type { CommercialDecisions, FollowupPreview } from '../types/decisions'
