import type { FederalRoute } from '../types/api'

export type Surface = 'today' | 'opportunities' | 'accounts' | 'intelligence' | 'map' | 'actions' | 'communications' | 'settings' | 'monitor'
export type LocationScope = 'ACCOUNT' | 'FACILITY'
export type NavigationMode = 'push' | 'replace' | 'none'

export interface AssessmentLocation { assessmentId: string; assessmentVersion: number; eventId: string; accountId: string }
export interface FederalLocation { opportunityId: string; assessmentId: string; assessmentVersion: number; routeType: FederalRoute['route_type']; accountId?: string; partnershipId?: string }
export interface RelationshipLocation { pathId?: string; mode?: string; startAccountId?: string }
export interface WorkspaceLocation {
  surface: Surface
  accountId?: string
  assessment?: AssessmentLocation
  eventId?: string
  federal?: FederalLocation
  partnershipId?: string
  facilityId?: string
  scope?: LocationScope
  relationship?: RelationshipLocation
  actionId?: string
  recordId?: string
  subview?: string
  filters?: Record<string, string | string[]>
  sort?: string
  returnTo?: WorkspaceLocation
  anchor?: string
}
export interface DecodedWorkspaceLocation { location: WorkspaceLocation; canonicalHash: string; recovery?: 'malformed' | 'unsupported' }

const surfaces = new Set<Surface>(['today', 'opportunities', 'accounts', 'intelligence', 'map', 'actions', 'communications', 'settings', 'monitor'])
const routeTypes = new Set<FederalRoute['route_type']>(['DIRECT_BTX', 'CUSTOMER_EXPANSION', 'STRATEGIC_PARTNER', 'NEW_PROSPECT', 'MARKET_WATCH'])
const allowedSubviews: Record<Surface, Set<string>> = {
  opportunities: new Set(), today: new Set(['recovery']), accounts: new Set(['overview', 'partnership', 'relationships', 'record']),
  intelligence: new Set(['monitor', 'brief', 'federal', 'markets']), map: new Set(['map', 'list']),
  actions: new Set(['actions', 'suggestions', 'completed']), communications: new Set(),
  settings: new Set(['personal', 'access', 'integrations']), monitor: new Set(),
}
const allowedFilterKeys = new Set(['profileTab', 'lane', 'kind', 'account', 'business_unit', 'market', 'metric', 'average', 'compare', 'customer', 'source', 'timing', 'status', 'priority', 'query', 'notice_type', 'fiscal_year', 'classification', 'industry', 'industries', 'relationships', 'layers', 'signal_timing', 'naics', 'business_units', 'capabilities', 'fulfillment', 'radius', 'scope', 'partnership', 'shortlist', 'top100', 'coverage', 'page', 'validation_page', 'sort_direction', 'suggestion_view'])
const idPattern = /^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,199}$/
const safeValue = (value: string) => value.length <= 200 && [...value].every(character => character >= ' ' && character !== '\u007f')

function safeId(value: string | null): string | undefined {
  if (!value) return undefined
  try { const decoded = decodeURIComponent(value); return idPattern.test(decoded) && decoded !== '..' && decoded !== '.' ? decoded : undefined } catch { return undefined }
}
function positiveInteger(value: string | null): number | undefined {
  if (!value || !/^\d{1,9}$/.test(value)) return undefined
  const parsed = Number(value); return parsed > 0 ? parsed : undefined
}
function filterValues(params: URLSearchParams): Record<string, string | string[]> | undefined {
  const result: Record<string, string | string[]> = {}
  for (const [parameter, value] of params.entries()) {
    if (!parameter.startsWith('f.') || !allowedFilterKeys.has(parameter.slice(2)) || !safeValue(value)) continue
    const key = parameter.slice(2); const current = result[key]
    result[key] = current === undefined ? value : Array.isArray(current) ? [...current, value] : [current, value]
  }
  return Object.keys(result).length ? result : undefined
}
function queryLocation(surface: Surface, params: URLSearchParams, accountId?: string): { location: WorkspaceLocation; invalid: boolean } {
  let invalid = false
  const readId = (name: string) => { const raw = params.get(name); const value = safeId(raw); if (raw && !value) invalid = true; return value }
  accountId ??= readId('account_id')
  const subviewRaw = params.get('view'); const subview = subviewRaw && allowedSubviews[surface].has(subviewRaw) ? subviewRaw : undefined
  if (subviewRaw && !subview) invalid = true
  const assessmentId = readId('assessment'); const assessmentVersion = positiveInteger(params.get('av')); const eventId = readId('event'); const assessmentAccountId = readId('aa') ?? accountId
  const assessment = assessmentId && assessmentVersion && eventId && assessmentAccountId ? { assessmentId, assessmentVersion, eventId, accountId: assessmentAccountId } : undefined
  // An event can be selected before an account-scoped assessment exists (for
  // example, from the map).  Only partial assessment tuples are malformed.
  if ((assessmentId || assessmentVersion) && !assessment) invalid = true
  const opportunityId = readId('opportunity'); const federalAssessmentId = readId('fa'); const federalAssessmentVersion = positiveInteger(params.get('fav')); const routeRaw = params.get('route')
  const routeType = routeRaw && routeTypes.has(routeRaw as FederalRoute['route_type']) ? routeRaw as FederalRoute['route_type'] : undefined
  if (routeRaw && !routeType) invalid = true
  const federal = opportunityId && federalAssessmentId && federalAssessmentVersion && routeType ? { opportunityId, assessmentId: federalAssessmentId, assessmentVersion: federalAssessmentVersion, routeType, accountId: readId('ra'), partnershipId: readId('partner') } : undefined
  if ([opportunityId, federalAssessmentId, federalAssessmentVersion, routeType].some(Boolean) && !federal) invalid = true
  const scopeRaw = params.get('scope'); const facilityId = readId('facility')
  const scope = scopeRaw === 'facility' && facilityId ? 'FACILITY' : scopeRaw === 'account' || accountId ? 'ACCOUNT' : undefined
  if (scopeRaw && !['facility', 'account'].includes(scopeRaw)) invalid = true
  if (scopeRaw === 'facility' && !facilityId) invalid = true
  const pathId = readId('path'); const relationshipMode = readId('relationship_mode'); const relationshipStart = readId('relationship_start')
  const relationship = pathId || relationshipMode || relationshipStart ? { pathId, mode: relationshipMode, startAccountId: relationshipStart } : undefined
  const returnHash = params.get('return'); let returnTo: WorkspaceLocation | undefined
  if (returnHash) { const decoded = decodeWorkspaceLocation(returnHash, false); if (!decoded.recovery) returnTo = { ...decoded.location, returnTo: undefined }; else invalid = true }
  return { location: { surface, accountId, assessment, eventId: assessment?.eventId ?? eventId, federal, partnershipId: readId('partnership') ?? federal?.partnershipId, facilityId, scope, relationship, actionId: readId('action'), recordId: readId('record'), subview, filters: filterValues(params), sort: readId('sort'), returnTo, anchor: readId('anchor') }, invalid }
}

export function decodeWorkspaceLocation(hash: string, allowReturn = true): DecodedWorkspaceLocation {
  const raw = hash.startsWith('#') ? hash.slice(1) : hash
  const [pathRaw, queryRaw = ''] = raw.replace(/^\/?/, '').split('?', 2); const parts = pathRaw.split('/').filter(Boolean)
  const surface = surfaces.has(parts[0] as Surface) ? parts[0] as Surface : 'today'; let invalid = Boolean(parts[0] && !surfaces.has(parts[0] as Surface)); const params = new URLSearchParams(queryRaw)
  let accountId: string | undefined
  if (surface === 'accounts' && parts[1]) accountId = safeId(parts[1])
  if (surface === 'accounts' && parts[1] && !accountId) invalid = true
  if (parts.length > (surface === 'accounts' ? 2 : 1)) {
    if (surface === 'today' && parts[1] === 'brief' && safeId(parts[2])) { params.set('view', 'recovery'); params.set('record', safeId(parts[2])!) }
    else if (surface === 'intelligence' && ['federal', 'markets'].includes(parts[1]) && parts.length === 2) params.set('view', parts[1])
    else if (surface === 'intelligence' && parts[1] === 'brief' && safeId(parts[2])) { params.set('view', 'brief'); params.set('record', safeId(parts[2])!) }
    else if (surface === 'settings' && allowedSubviews.settings.has(parts[1]) && parts.length === 2) params.set('view', parts[1])
    else invalid = true
  }
  const parsed = queryLocation(surface, params, accountId); invalid ||= parsed.invalid
  if (!allowReturn) parsed.location.returnTo = undefined
  const canonicalHash = workspaceHash(parsed.location)
  return { location: parsed.location, canonicalHash, recovery: invalid ? 'malformed' : undefined }
}
export function workspaceLocation(hash: string): WorkspaceLocation { return decodeWorkspaceLocation(hash).location }
function appendId(params: URLSearchParams, key: string, value?: string) { if (value && idPattern.test(value)) params.set(key, value) }
export function workspaceHash(locationOrSurface: WorkspaceLocation | Surface, legacyAccountId?: string): string {
  const location: WorkspaceLocation = typeof locationOrSurface === 'string' ? { surface: locationOrSurface, accountId: legacyAccountId } : locationOrSurface; const params = new URLSearchParams()
  if (location.subview && allowedSubviews[location.surface].has(location.subview)) params.set('view', location.subview)
  if (location.surface !== 'accounts') appendId(params, 'account_id', location.accountId)
  appendId(params, 'event', location.assessment?.eventId ?? location.eventId)
  if (location.assessment) { appendId(params, 'assessment', location.assessment.assessmentId); params.set('av', String(location.assessment.assessmentVersion)); if (location.assessment.accountId !== location.accountId) appendId(params, 'aa', location.assessment.accountId) }
  if (location.federal) { appendId(params, 'opportunity', location.federal.opportunityId); appendId(params, 'fa', location.federal.assessmentId); params.set('fav', String(location.federal.assessmentVersion)); params.set('route', location.federal.routeType); appendId(params, 'ra', location.federal.accountId); appendId(params, 'partner', location.federal.partnershipId) }
  appendId(params, 'partnership', location.partnershipId); appendId(params, 'facility', location.facilityId); if (location.scope) params.set('scope', location.scope.toLowerCase())
  appendId(params, 'path', location.relationship?.pathId); appendId(params, 'relationship_mode', location.relationship?.mode); appendId(params, 'relationship_start', location.relationship?.startAccountId)
  appendId(params, 'action', location.actionId); appendId(params, 'record', location.recordId); appendId(params, 'sort', location.sort); appendId(params, 'anchor', location.anchor)
  for (const [key, raw] of Object.entries(location.filters ?? {}).sort(([a], [b]) => a.localeCompare(b))) { if (!allowedFilterKeys.has(key)) continue; for (const value of Array.isArray(raw) ? raw : [raw]) if (safeValue(value)) params.append(`f.${key}`, value) }
  if (location.returnTo) params.set('return', workspaceHash({ ...location.returnTo, returnTo: undefined }))
  const accountSegment = location.surface === 'accounts' && location.accountId && idPattern.test(location.accountId) ? `/${encodeURIComponent(location.accountId)}` : ''; const query = params.toString()
  return `#/${location.surface}${accountSegment}${query ? `?${query}` : ''}`
}
export function sameWorkspaceLocation(left: WorkspaceLocation, right: WorkspaceLocation): boolean { return workspaceHash(left) === workspaceHash(right) }
export function historyUpdate(currentHash: string, next: WorkspaceLocation, mode: NavigationMode): { method: NavigationMode; hash: string } {
  const hash = workspaceHash(next); if (mode === 'none' || decodeWorkspaceLocation(currentHash).canonicalHash === hash) return { method: 'none', hash }; return { method: mode, hash }
}
