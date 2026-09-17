import { useCallback, useEffect, useRef, useState } from 'react'
import { api, resolveFederalAssessment } from '../api/client'
import { OmniDrawer } from '../components/OmniDrawer'
import { Button, Disclosure, StatusMessage } from '../components/UI'
import { deferredSurface } from '../components/deferredSurface'
import type { PortfolioSnapshot } from '../features/accounts/Accounts'
import { DEFAULT_MAP_LAYERS, type MapFilters, type MapLayer, type MapViewSnapshot } from '../features/map/mapModel'
import { Today, type TodayFilters } from '../features/today/Today'
import { decodeWorkspaceLocation, historyUpdate, sameWorkspaceLocation, type NavigationMode, type Surface, type WorkspaceLocation } from './navigation'
import { authorizedDestinations, canOpenDestination, type NavigationAuthority } from './destinations'
import type { Account, Account360, Alert, BtxMapFacility, CommandCenter, CommunicationDraft, FederalAssessment, FederalOpportunity, FederalRoute, MapAccountSegment, MapIntelligence, MapRecord, MonitorHealth, OmniAssessmentSelection, OmniContext, OmniFederalSelection, OmniSurface, Principal, PublicLocation, Signal, Suggestion, WorkItem, WorkspaceSettings } from '../types/api'
import '../design/tokens.css'
import '../design/app.css'
import '../design/shell.css'
import '../design/mobile.css'
const Accounts = deferredSurface(() => import('../features/accounts/Accounts').then(module => module.Accounts), 'Customers & Prospects', 'Accounts')
const Map = deferredSurface(() => import('../features/map/Map').then(module => module.Map), 'Map', 'Map')
const Actions = deferredSurface(() => import('../features/actions/Actions').then(module => module.Actions), 'Actions', 'Actions')
const Communications = deferredSurface(() => import('../features/communications/Communications').then(module => module.Communications), 'Communications', 'Communications')
const Intelligence = deferredSurface(() => import('../features/intelligence/Intelligence').then(module => module.Intelligence), 'Intelligence', 'Intelligence')
const Monitor = deferredSurface(() => import('../features/monitor/Monitor').then(module => module.Monitor), 'Source Health', 'Source Health')
const Settings = deferredSurface(() => import('../features/settings/Settings').then(module => module.Settings), 'Settings', 'Settings')
type OmniViewContext = Pick<OmniContext, 'selected_event_id' | 'selected_assessment' | 'selected_federal_opportunity' | 'selected_program_id' | 'active_filters' | 'visible_record_ids' | 'relationship_selection'>
const surfaceLabels: Record<Surface, string> = {
  today: 'Today',
  accounts: 'Customers & Prospects',
  intelligence: 'Intelligence',
  map: 'Map',
  actions: 'Actions',
  communications: 'Communications',
  settings: 'Settings',
  monitor: 'Source Health',
}
const portfolioSnapshotFromLocation = (location: WorkspaceLocation): PortfolioSnapshot | undefined => {
  if (location.surface !== 'accounts' || location.accountId) return undefined
  const filters = location.filters ?? {}; const sortKey = ['name', 'classification', 'industry', 'attractiveness', 'priority', 'evidence'].includes(location.sort ?? '') ? location.sort as PortfolioSnapshot['sortKey'] : 'name'
  return { query: String(filters.query ?? ''), scope: filters.coverage === 'RICH' ? 'RICH' : 'ALL', industry: String(filters.industry ?? 'ALL'), entity: ['CUSTOMER', 'PROSPECT', 'UNAVAILABLE'].includes(String(filters.classification)) ? String(filters.classification) as PortfolioSnapshot['entity'] : 'ALL', top100: filters.top100 === 'true', partnershipScope: ['EXCLUDE', 'ONLY'].includes(String(filters.partnership)) ? String(filters.partnership) as NonNullable<PortfolioSnapshot['partnershipScope']> : 'ALL', shortlistOnly: filters.shortlist === 'true', sortKey, sortDirection: filters.sort_direction === 'descending' ? 'descending' : 'ascending', filtersOpen: false, page: Number(filters.page ?? 1) || 1 }
}
const values = (value: string | string[] | undefined) => value === undefined ? [] : Array.isArray(value) ? value : [value]
const mapSnapshotFromLocation = (location: WorkspaceLocation): MapViewSnapshot | undefined => {
  if (location.surface !== 'map') return undefined
  const source = location.filters ?? {}; const radius = Number(source.radius)
  const filters: MapFilters = {
    coverage: source.coverage === 'RICH' ? 'RICH' : 'ALL', top100: source.top100 === 'true', industries: values(source.industries),
    relationships: values(source.relationships) as MapAccountSegment[], layers: (values(source.layers).length ? values(source.layers) : DEFAULT_MAP_LAYERS) as MapLayer[], signalTiming: (values(source.signal_timing).length ? values(source.signal_timing) : ['CURRENT', 'UPCOMING']) as Array<'CURRENT' | 'UPCOMING'>,
    strategicPartnership: ['EXCLUDE', 'ONLY'].includes(String(source.partnership)) ? String(source.partnership) as 'EXCLUDE' | 'ONLY' : 'ALL', shortlistOnly: source.shortlist === 'true', radiusMiles: [30, 50, 100].includes(radius) ? radius as 30 | 50 | 100 : undefined,
    naicsCodes: values(source.naics), businessUnitIds: values(source.business_units), fulfillmentStates: values(source.fulfillment),
  }
  return { filters }
}
const todayFiltersFromLocation = (location: WorkspaceLocation): TodayFilters => ({ kind: ['PUBLIC_SIGNAL', 'COMMERCIAL_REVIEW'].includes(String(location.filters?.kind)) ? String(location.filters?.kind) as TodayFilters['kind'] : 'ALL', accountId: String(location.filters?.account ?? ''), businessUnit: String(location.filters?.business_unit ?? ''), query: String(location.filters?.query ?? ''), sort: ['RECENT', 'OLDEST', 'CUSTOMER_ASC', 'CUSTOMER_DESC'].includes(location.sort ?? '') ? location.sort as TodayFilters['sort'] : 'RANKED', page: Number(location.filters?.page ?? 1) || 1, validationPage: Number(location.filters?.validation_page ?? 1) || 1 })
export default function App() {
  const initialLocation = decodeWorkspaceLocation(window.location.hash)
  const [authState, setAuthState] = useState<'checking' | 'authenticated' | 'required'>(import.meta.env.DEV ? 'authenticated' : 'checking')
  const [commandCenter, setCommandCenter] = useState<CommandCenter>()
  const [todayState, setTodayState] = useState<'loading' | 'loaded' | 'unavailable'>('loading')
  const [todayFilters, setTodayFilters] = useState<TodayFilters>(() => todayFiltersFromLocation(initialLocation.location))
  const [location, setLocation] = useState<WorkspaceLocation>(initialLocation.location)
  const locationRef = useRef(location)
  const surface = location.surface
  const [linkRecovery, setLinkRecovery] = useState(initialLocation.recovery ? 'This link could not be restored completely. A safe workspace view is shown instead.' : '')
  const [workspaceMenuOpen, setWorkspaceMenuOpen] = useState(false)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [portfolioSnapshot, setPortfolioSnapshot] = useState<PortfolioSnapshot | undefined>(() => portfolioSnapshotFromLocation(initialLocation.location))
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [signals, setSignals] = useState<Signal[]>([])
  const [records, setRecords] = useState<MapRecord[]>([])
  const [pendingMapAccounts, setPendingMapAccounts] = useState<import('../types/api').PendingMapAccount[]>([])
  const [mapViewSnapshot, setMapViewSnapshot] = useState<MapViewSnapshot | undefined>(() => mapSnapshotFromLocation(initialLocation.location))
  const [publicLocations, setPublicLocations] = useState<PublicLocation[]>([])
  const [btxFacilities, setBtxFacilities] = useState<BtxMapFacility[]>([])
  const [mapSignals, setMapSignals] = useState<MapIntelligence[]>([])
  const [layers, setLayers] = useState<string[]>([])
  const [detail, setDetail] = useState<Account360>()
  const [items, setItems] = useState<WorkItem[]>([])
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [communications, setCommunications] = useState<CommunicationDraft[]>([])
  const [workspaceSettings, setWorkspaceSettings] = useState<WorkspaceSettings>()
  const [settingsState, setSettingsState] = useState<'loading' | 'loaded' | 'error'>('loading')
  const [actionPrincipal, setActionPrincipal] = useState<Principal>()
  const [actionWarning, setActionWarning] = useState('Actions use durable governed storage.')
  const [monitor, setMonitor] = useState<MonitorHealth>()
  const navigationAuthority: NavigationAuthority = { authenticated: authState === 'authenticated', sourceHealth: workspaceSettings?.capabilities.view_source_health === true }
  const destinations = authorizedDestinations(navigationAuthority)
  const desktopPrimaryDestinations = destinations.filter(destination => destination.desktop === 'primary')
  const desktopSecondaryDestinations = destinations.filter(destination => destination.desktop === 'secondary')
  const mobilePrimaryDestinations = destinations.filter(destination => destination.mobile === 'primary')
  const mobileSecondaryDestinations = destinations.filter(destination => destination.mobile === 'secondary')
  const [error, setError] = useState('')
  const [resourceState, setResourceState] = useState<Partial<Record<Surface, 'loading' | 'loaded' | 'error'>>>({})
  const [resourceReady, setResourceReady] = useState<Partial<Record<Surface, boolean>>>({})
  const [resourceRefresh, setResourceRefresh] = useState<{ key: Surface; version: number }>()
  const [accountOpening, setAccountOpening] = useState<string>()
  const accountRequest = useRef<AbortController | undefined>(undefined)
  const [selectedEventId, setSelectedEventId] = useState<string>()
  const [selectedMapAccountId, setSelectedMapAccountId] = useState<string>()
  const [selectedMapFacilityId, setSelectedMapFacilityId] = useState<string>()
  const [selectedActionId, setSelectedActionId] = useState<string>()
  const [actionSourceAlertId, setActionSourceAlertId] = useState<string>()
  const [viewContext, setViewContext] = useState<OmniViewContext>({})
  useEffect(() => { locationRef.current = location }, [location])
  const commitLocation = useCallback((next: WorkspaceLocation, mode: NavigationMode = 'push') => {
    if (sameWorkspaceLocation(locationRef.current, next)) return
    const update = historyUpdate(window.location.hash, next, mode)
    if (update.method === 'none' && update.hash === decodeWorkspaceLocation(window.location.hash).canonicalHash) return
    if (update.method === 'push') window.history.pushState({ btxOmniNavigation: true }, '', update.hash)
    else if (update.method === 'replace') window.history.replaceState({ btxOmniNavigation: true }, '', update.hash)
    setLocation(next)
    setLinkRecovery('')
  }, [])
  const applyWorkspaceSettings = useCallback((value: WorkspaceSettings) => {
    setWorkspaceSettings(value)
    setActionPrincipal(value.principal)
    setSettingsState('loaded')
  }, [])
  const clearSelectedEvent = useCallback(() => setSelectedEventId(undefined), [])
  const clearMapSelection = useCallback(() => {
    setSelectedMapAccountId(undefined)
    setSelectedMapFacilityId(undefined)
  }, [])
  const clearSelectedAction = useCallback(() => { setSelectedActionId(undefined); setActionSourceAlertId(undefined) }, [])
  const clearViewContext = useCallback(() => setViewContext({}), [])
  const selectMapFacility = useCallback((facilityId?: string, accountId?: string) => { setSelectedMapFacilityId(facilityId); setSelectedMapAccountId(accountId) }, [])
  const updateMapSnapshot = useCallback((snapshot: MapViewSnapshot) => {
    setMapViewSnapshot(snapshot)
    commitLocation({ ...locationRef.current, filters: { ...(snapshot.filters.coverage !== 'ALL' ? { coverage: snapshot.filters.coverage } : {}), ...(snapshot.filters.top100 ? { top100: 'true' } : {}), ...(snapshot.filters.industries.length ? { industries: snapshot.filters.industries } : {}), ...(snapshot.filters.relationships.length ? { relationships: snapshot.filters.relationships } : {}), ...(snapshot.filters.layers.length ? { layers: snapshot.filters.layers } : {}), ...(snapshot.filters.signalTiming.length ? { signal_timing: snapshot.filters.signalTiming } : {}), ...(snapshot.filters.naicsCodes?.length ? { naics: snapshot.filters.naicsCodes } : {}), ...(snapshot.filters.businessUnitIds?.length ? { business_units: snapshot.filters.businessUnitIds } : {}), ...(snapshot.filters.fulfillmentStates?.length ? { fulfillment: snapshot.filters.fulfillmentStates } : {}), ...(snapshot.filters.radiusMiles ? { radius: String(snapshot.filters.radiusMiles) } : {}), ...(snapshot.filters.strategicPartnership && snapshot.filters.strategicPartnership !== 'ALL' ? { partnership: snapshot.filters.strategicPartnership } : {}), ...(snapshot.filters.shortlistOnly ? { shortlist: 'true' } : {}) }, accountId: snapshot.selected?.accountId, facilityId: snapshot.selected?.facilityId, eventId: snapshot.selected?.eventId, scope: snapshot.selected?.facilityId ? 'FACILITY' : snapshot.selected?.accountId ? 'ACCOUNT' : undefined }, 'replace')
  }, [commitLocation])
  const updateMapAccount = useCallback((id?: string) => {
    setSelectedMapAccountId(id); setSelectedMapFacilityId(undefined)
    commitLocation({ ...locationRef.current, accountId: id, facilityId: undefined, scope: id ? 'ACCOUNT' : undefined }, 'replace')
  }, [commitLocation])
  const updateMapFacility = useCallback((facilityId?: string, accountId?: string) => {
    selectMapFacility(facilityId, accountId)
    commitLocation({ ...locationRef.current, accountId, facilityId, scope: facilityId ? 'FACILITY' : accountId ? 'ACCOUNT' : undefined }, 'replace')
  }, [commitLocation, selectMapFacility])
  const updateMapEvent = useCallback((eventId?: string) => {
    setSelectedEventId(eventId); commitLocation({ ...locationRef.current, eventId }, 'replace')
  }, [commitLocation])
  const select = useCallback(async (id: string, recordHistory = true, assessment?: OmniAssessmentSelection, federal?: OmniFederalSelection, subview?: WorkspaceLocation['subview'], suppliedFederalAssessment?: FederalAssessment) => {
    accountRequest.current?.abort()
    const controller = new AbortController(); accountRequest.current = controller
    setAccountOpening(id)
    try {
      setError('')
      const result = await api.account(id, controller.signal)
      const federalAssessment = suppliedFederalAssessment ?? (federal ? await resolveFederalAssessment(federal, controller.signal).catch(() => undefined) : undefined)
      if (controller.signal.aborted) return
      if (assessment) setSelectedEventId(assessment.event_id)
      else clearSelectedEvent()
      clearMapSelection()
      clearSelectedAction()
      const exactFederal = !federal || (federalAssessment?.assessment_id === federal.assessment_id && federalAssessment.assessment_version === federal.assessment_version && federalAssessment.opportunity_id === federal.opportunity_id)
      if (federal && exactFederal) setViewContext({ selected_federal_opportunity: federal })
      else if (assessment) setViewContext({ selected_event_id: assessment.event_id, selected_assessment: assessment })
      else clearViewContext()
      if (federal && !exactFederal) setLinkRecovery('The selected federal assessment version is no longer available in your authorized scope. The organization remains open without substituting another assessment.')
      setDetail(federalAssessment && exactFederal ? { ...result, federal_opportunities: [federalAssessment, ...(result.federal_opportunities ?? []).filter(item => item.assessment_id !== federalAssessment.assessment_id)] } : result)
      const origin = locationRef.current
      const next: WorkspaceLocation = {
        surface: 'accounts', accountId: id, scope: origin.surface === 'map' && origin.facilityId ? 'FACILITY' : 'ACCOUNT',
        facilityId: origin.surface === 'map' ? origin.facilityId : undefined,
        assessment: assessment ? { assessmentId: assessment.assessment_id, assessmentVersion: assessment.assessment_version, eventId: assessment.event_id, accountId: assessment.account_id } : undefined,
        eventId: assessment?.event_id,
        federal: federal && exactFederal ? { opportunityId: federal.opportunity_id, assessmentId: federal.assessment_id, assessmentVersion: federal.assessment_version, routeType: federal.route_type, accountId: federal.account_id ?? undefined, partnershipId: federal.partnership_id ?? undefined } : undefined,
        partnershipId: federal?.partnership_id ?? undefined,
        subview,
        returnTo: recordHistory ? { ...origin, returnTo: undefined } : origin.returnTo,
      }
      commitLocation(next, recordHistory ? 'push' : 'none')
    } catch (err) {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Customer context unavailable.')
    } finally { if (accountRequest.current === controller) setAccountOpening(undefined) }
  }, [clearSelectedEvent, clearMapSelection, clearSelectedAction, clearViewContext, commitLocation])
  const navigate = useCallback((id: Surface, recordHistory = true) => {
    const authority: NavigationAuthority = { authenticated: authState === 'authenticated', sourceHealth: workspaceSettings?.capabilities.view_source_health === true }
    if (!canOpenDestination(id, authority)) {
      commitLocation({ surface: 'today' }, 'replace')
      setLinkRecovery('This workspace is unavailable for your current access. No operational details were disclosed.')
      return
    }
    accountRequest.current?.abort(); setAccountOpening(undefined)
    setWorkspaceMenuOpen(false)
    if (id !== surface || (id === 'accounts' && detail)) {
      clearSelectedEvent()
      clearMapSelection()
      clearSelectedAction()
      clearViewContext()
      setDetail(undefined)
    }
    commitLocation({ surface: id }, recordHistory ? 'push' : 'none')
  }, [authState, workspaceSettings?.capabilities.view_source_health, surface, detail, clearSelectedEvent, clearMapSelection, clearSelectedAction, clearViewContext, commitLocation])
  const createIntelligenceAction = useCallback(async (brief: import('../types/api').MonitorSignalBrief) => {
    const accountId = brief.canonical_account_ids[0]
    if (!accountId || !brief.assessment_id || !brief.recommended_action) {
      setError('A current account-specific Intelligence assessment with a supported next step is required.')
      return
    }
    try {
      setError('')
      const created = await api.createAction({
        account_id: accountId,
        title: brief.recommended_action,
        description: `${brief.why_it_may_matter}${brief.action_rationale ? ` ${brief.action_rationale}` : ''}`,
        priority: brief.commercial_relevance_state === 'ESTABLISHED_ACCOUNT_REVIEW' ? 'HIGH' : 'MEDIUM',
        evidence_ids: [brief.assessment_id, ...brief.evidence_ids],
        context_referents: [['intelligence_assessment', brief.assessment_id], ['intelligence_event', brief.id]],
        approval_required: false,
        idempotency_key: `monitor-${brief.assessment_id.slice(0, 56)}`,
      })
      setItems(current => current.some(item => item.id === created.id) ? current : [created, ...current])
      setActionWarning('Action proposal created from the current Intelligence assessment. Review ownership and due date before execution.')
      commitLocation({ surface: 'actions', actionId: created.id, returnTo: { ...locationRef.current, returnTo: undefined } }, 'push')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The action proposal could not be created.')
    }
  }, [commitLocation])
  const createFederalAction = useCallback(async (opportunity: FederalOpportunity, route: FederalRoute) => {
    const assessment = opportunity.assessment
    if (!assessment || !route.account_id) {
      setError('This route does not establish an organization for a governed Action proposal.')
      return
    }
    const referents: Array<[string, string]> = [
      ['federal_opportunity', opportunity.opportunity_id],
      ['federal_assessment', assessment.assessment_id],
      ['federal_assessment_version', String(assessment.assessment_version)],
      ['federal_route_type', route.route_type],
    ]
    if (route.route_type === 'STRATEGIC_PARTNER') referents.push(['strategic_partnership', route.account_id])
    try {
      const created = await api.createAction({
        account_id: route.account_id,
        title: route.governed_action,
        description: `${opportunity.title}. ${route.why} Unknowns: ${route.unknowns.join('; ') || 'No additional route gaps recorded.'}`,
        priority: opportunity.stage.code === 'SOLICITATION' ? 'HIGH' : 'MEDIUM',
        evidence_ids: [assessment.assessment_id, ...(assessment.evidence_references ?? [])],
        context_referents: referents,
        approval_required: false,
        idempotency_key: `federal-${assessment.assessment_id.slice(0, 40)}-${route.route_type.toLowerCase()}`,
      })
      setItems(current => current.some(item => item.id === created.id) ? current : [created, ...current])
      setActionWarning('Federal opportunity validation proposal restored from its canonical assessment. No external write was performed.')
      setSelectedActionId(created.id)
      commitLocation({ surface: 'actions', actionId: created.id, federal: { opportunityId: assessment.opportunity_id, assessmentId: assessment.assessment_id, assessmentVersion: assessment.assessment_version, routeType: route.route_type, accountId: route.account_id ?? undefined, partnershipId: route.route_type === 'STRATEGIC_PARTNER' ? route.account_id ?? undefined : undefined }, returnTo: { ...locationRef.current, returnTo: undefined } }, 'push')
    } catch (err) { setError(err instanceof Error ? err.message : 'The federal Action proposal could not be created.') }
  }, [commitLocation])
  useEffect(() => {
    if (authState !== 'authenticated') return
    const restore = () => {
      const decoded = decodeWorkspaceLocation(window.location.hash)
      if (decoded.recovery) setLinkRecovery('This link is malformed or no longer supported. A safe workspace view is shown instead.')
      if (window.location.hash !== decoded.canonicalHash) window.history.replaceState({ btxOmniNavigation: true }, '', decoded.canonicalHash)
      if (!decoded.location.accountId) { setDetail(undefined); clearSelectedEvent(); clearMapSelection(); clearSelectedAction(); clearViewContext() }
      setLocation(decoded.location)
      if (decoded.location.surface === 'today') setTodayFilters(todayFiltersFromLocation(decoded.location))
    }
    restore()
    window.addEventListener('hashchange', restore)
    window.addEventListener('popstate', restore)
    return () => { window.removeEventListener('hashchange', restore); window.removeEventListener('popstate', restore) }
  }, [authState, clearMapSelection, clearSelectedAction, clearSelectedEvent, clearViewContext])
  useEffect(() => {
    if (authState !== 'authenticated') return
    if (!location.accountId) return
    const controller = new AbortController(); accountRequest.current = controller
    const federalSelection: OmniFederalSelection | undefined = location.federal ? { opportunity_id: location.federal.opportunityId, assessment_id: location.federal.assessmentId, assessment_version: location.federal.assessmentVersion, route_type: location.federal.routeType, account_id: location.federal.accountId, partnership_id: location.federal.partnershipId } : undefined
    const federalRequest = federalSelection ? resolveFederalAssessment(federalSelection, controller.signal).catch(() => undefined) : Promise.resolve(undefined)
    void Promise.all([api.account(location.accountId, controller.signal), federalRequest]).then(([result, federalAssessment]) => {
      if (controller.signal.aborted) return
      const assessment = location.assessment
      const exactAssessment = !assessment || result.customer_360.intelligence.some(item => item.business_briefing?.assessment_id === assessment.assessmentId && item.business_briefing?.assessment_version === assessment.assessmentVersion)
      const federal = location.federal
      const exactFederal = !federal || (federalAssessment?.assessment_id === federal.assessmentId && federalAssessment.assessment_version === federal.assessmentVersion && federalAssessment.opportunity_id === federal.opportunityId)
      if (!exactAssessment || !exactFederal) {
        setLinkRecovery('The selected investigation version is no longer available in your authorized scope. The organization remains open without substituting a newer assessment.')
      }
      setDetail(federalAssessment && exactFederal ? { ...result, federal_opportunities: [federalAssessment, ...(result.federal_opportunities ?? []).filter(item => item.assessment_id !== federalAssessment.assessment_id)] } : result)
      setSelectedEventId(exactAssessment ? assessment?.eventId : undefined)
      setSelectedMapFacilityId(location.facilityId)
      setViewContext({
        selected_event_id: exactAssessment ? assessment?.eventId : undefined,
        selected_assessment: exactAssessment && assessment ? { assessment_id: assessment.assessmentId, assessment_version: assessment.assessmentVersion, event_id: assessment.eventId, account_id: assessment.accountId } : undefined,
        selected_federal_opportunity: exactFederal && federal ? { opportunity_id: federal.opportunityId, assessment_id: federal.assessmentId, assessment_version: federal.assessmentVersion, route_type: federal.routeType, account_id: federal.accountId, partnership_id: federal.partnershipId } : undefined,
      })
    }).catch(() => {
      if (!controller.signal.aborted) setLinkRecovery('This organization is unavailable or you do not have access. No details from the link were disclosed.')
    })
    return () => controller.abort()
  }, [authState, location.accountId, location.assessment, location.facilityId, location.federal])
  useEffect(() => { if (import.meta.env.DEV) return; void api.session().then(() => setAuthState('authenticated')).catch(() => setAuthState('required')) }, [])
  useEffect(() => {
    if (authState !== 'authenticated') return
    const controller = new AbortController(); const { signal } = controller
    // Publish each independent read as it arrives. A slow optional surface must
    // not hold the entire workspace behind an all-settled loading screen.
    const load = <T,>(key: Surface, promise: Promise<T>, publish: (value: T) => void, failed?: () => void) => {
      void promise.then(value => { if (!signal.aborted) { publish(value); setResourceReady(old => ({ ...old, [key]: true })); setResourceState(old => ({ ...old, [key]: 'loaded' })) } }).catch(() => { if (!signal.aborted) { failed?.(); setResourceState(old => ({ ...old, [key]: 'error' })) } })
    }
    const requested = resourceRefresh?.key
    if (!requested || requested === 'accounts') load('accounts', api.accounts(signal), value => setAccounts(value.accounts))
    if (!requested || requested === 'today') load('today', api.today(signal), value => { setAlerts(value.commercial_alerts); setCommandCenter(value.command_center); setTodayState('loaded') }, () => setTodayState(previous => previous === 'loaded' ? previous : 'unavailable'))
    if (!requested || requested === 'intelligence') load('intelligence', api.intelligence(signal), value => setSignals(value.signals))
    if (!requested || requested === 'map') load('map', api.map(undefined, signal), value => { setRecords(value.accounts); setPendingMapAccounts(value.pending_accounts ?? []); setPublicLocations(value.facilities); setBtxFacilities(value.btx_facilities); setMapSignals(value.intelligence); setLayers(value.layers) })
    if (!requested || requested === 'actions') load('actions', api.actions(signal), value => { setItems(value.items); setSuggestions(value.suggestions); setActionPrincipal(value.principal); setActionWarning(value.warning) })
    if (!requested || requested === 'communications') load('communications', api.communications(signal), value => setCommunications(value.items))
    if (!requested || requested === 'settings') load('settings', api.settings(signal), applyWorkspaceSettings, () => setSettingsState('error'))
    return () => controller.abort()
  }, [applyWorkspaceSettings, authState, resourceRefresh])
  useEffect(() => {
    if (authState !== 'authenticated' || !workspaceSettings?.capabilities.view_source_health) return
    if (resourceRefresh && resourceRefresh.key !== 'monitor') return
    const controller = new AbortController()
    void api.monitor(controller.signal).then(value => {
      if (controller.signal.aborted) return
      setMonitor(value)
      setResourceReady(previous => ({ ...previous, monitor: true }))
      setResourceState(previous => ({ ...previous, monitor: 'loaded' }))
    }).catch(() => {
      if (!controller.signal.aborted) setResourceState(previous => ({ ...previous, monitor: 'error' }))
    })
    return () => controller.abort()
  }, [authState, workspaceSettings?.capabilities.view_source_health, resourceRefresh])
  useEffect(() => {
    if (settingsState !== 'loaded') return
    const sourceHealthDenied = location.surface === 'monitor' && !navigationAuthority.sourceHealth
    const integrationDetailDenied = location.surface === 'settings' && location.subview === 'integrations' && workspaceSettings?.capabilities.view_integration_diagnostics !== true
    if (!sourceHealthDenied && !integrationDetailDenied) return
    const timer = window.setTimeout(() => {
      commitLocation(integrationDetailDenied ? { surface: 'settings', subview: 'access' } : { surface: 'today' }, 'replace')
      setLinkRecovery('This workspace is unavailable for your current access. No operational details were disclosed.')
    }, 0)
    return () => window.clearTimeout(timer)
  }, [commitLocation, location.subview, location.surface, navigationAuthority.sourceHealth, settingsState, workspaceSettings?.capabilities.view_integration_diagnostics])
  useEffect(() => () => accountRequest.current?.abort(), [])
  if (authState === 'checking') return <main className="app-shell app-shell-loading"><div className="loading-stage"><span className="eyebrow">Secure workspace</span><h1>Checking hosted session</h1><p>Validating the server-held POC session without exposing role credentials.</p></div></main>
  if (authState === 'required') return <HostedSignIn onAuthenticated={() => window.location.reload()} />
  const locationAssessment: OmniAssessmentSelection | undefined = location.assessment ? { assessment_id: location.assessment.assessmentId, assessment_version: location.assessment.assessmentVersion, event_id: location.assessment.eventId, account_id: location.assessment.accountId } : undefined
  const locationFederal: OmniFederalSelection | undefined = location.federal ? { opportunity_id: location.federal.opportunityId, assessment_id: location.federal.assessmentId, assessment_version: location.federal.assessmentVersion, route_type: location.federal.routeType, account_id: location.federal.accountId, partnership_id: location.federal.partnershipId } : undefined
  const content =
    surface === 'accounts' ? (
      <Accounts accounts={accounts} detail={detail} initialAssessment={locationAssessment} initialFederal={locationFederal} initialSnapshot={portfolioSnapshot} onSnapshot={(snapshot) => { setPortfolioSnapshot(snapshot); if (!location.accountId) commitLocation({ surface: 'accounts', filters: { ...(snapshot.query ? { query: snapshot.query } : {}), ...(snapshot.scope === 'RICH' ? { coverage: snapshot.scope } : {}), ...(snapshot.industry !== 'ALL' ? { industry: snapshot.industry } : {}), ...(snapshot.entity !== 'ALL' ? { classification: snapshot.entity } : {}), ...(snapshot.top100 ? { top100: 'true' } : {}), ...(snapshot.partnershipScope && snapshot.partnershipScope !== 'ALL' ? { partnership: snapshot.partnershipScope } : {}), ...(snapshot.shortlistOnly ? { shortlist: 'true' } : {}), ...(snapshot.page && snapshot.page > 1 ? { page: String(snapshot.page) } : {}), ...(snapshot.sortDirection === 'descending' ? { sort_direction: snapshot.sortDirection } : {}) }, sort: snapshot.sortKey }, 'replace') }} onSelect={(id) => void select(id)} onBack={() => location.returnTo ? commitLocation(location.returnTo, 'push') : navigate('accounts')} onOmniContext={setViewContext} location={location} onLocationChange={commitLocation} />
    ) : surface === 'intelligence' ? (
      <Intelligence signals={signals} accounts={accounts} commandCenter={commandCenter} settings={workspaceSettings} onAccount={(id, assessment) => void select(id, true, assessment)} onEventSelect={setSelectedEventId} onCreateAction={(brief) => void createIntelligenceAction(brief)} onFederalAccount={(id, federal, federalAssessment) => void select(id, true, undefined, federal, 'overview', federalAssessment)} onFederalPartnership={(id, federal, federalAssessment) => void select(id, true, undefined, federal, 'partnership', federalAssessment)} onFederalRelationship={(id, federal, federalAssessment) => void select(id, true, undefined, federal, 'relationships', federalAssessment)} onFederalOmni={(federal) => { setViewContext({ selected_federal_opportunity: federal }); commitLocation({ ...location, federal: { opportunityId: federal.opportunity_id, assessmentId: federal.assessment_id, assessmentVersion: federal.assessment_version, routeType: federal.route_type, accountId: federal.account_id ?? undefined, partnershipId: federal.partnership_id ?? undefined } }, 'replace'); window.dispatchEvent(new Event('btx:open-omni')) }} onFederalAction={(opportunity, route) => void createFederalAction(opportunity, route)} onOmniContext={setViewContext} location={location} onLocationChange={commitLocation} />
    ) : surface === 'map' ? (
      <Map
        records={records}
        pendingAccounts={pendingMapAccounts}
        initialSnapshot={mapViewSnapshot}
        initialAccountId={location.accountId}
        initialFacilityId={location.facilityId}
        onSnapshot={updateMapSnapshot}
        publicLocations={publicLocations}
        btxFacilities={btxFacilities}
        layers={layers}
        signals={mapSignals}
        onAccount={(id, assessment) => void select(id, true, assessment)}
        onRelationships={(id) => void select(id)}
        onMapAccountSelect={updateMapAccount}
        onMapFacilitySelect={updateMapFacility}
        onMapEventSelect={updateMapEvent}
        onOmniContext={setViewContext}
      />
    ) : surface === 'actions' ? (
      <Actions items={items} suggestions={suggestions} principal={actionPrincipal} initialActionId={location.actionId ?? selectedActionId} onItem={(item) => setItems((old) => [...old.filter((value) => value.id !== item.id), item])} onSuggestions={setSuggestions} accounts={accounts} signals={signals} warning={actionWarning} onAccount={(id) => void select(id)} onActionSelect={setSelectedActionId} onOmniContext={setViewContext} sourceAlertId={actionSourceAlertId} onClearSource={() => setActionSourceAlertId(undefined)} location={location} onLocationChange={commitLocation} />
    ) : surface === 'communications' ? (
      <Communications accounts={accounts} principal={actionPrincipal} items={communications} onItem={(item) => setCommunications((old) => [...old.filter((value) => value.id !== item.id), item])} onAccount={(id) => void select(id)} />
    ) : surface === 'settings' ? (
      <Settings accounts={accounts} location={location} settings={workspaceSettings} state={settingsState} onSettings={applyWorkspaceSettings} onRetry={() => { setSettingsState('loading'); void api.settings().then(value => { applyWorkspaceSettings(value); setResourceReady(previous => ({ ...previous, settings: true })); setResourceState(previous => ({ ...previous, settings: 'loaded' })) }).catch(() => setSettingsState('error')) }} onSignOut={() => void api.signOut().then(() => { Object.keys(sessionStorage).filter(key => key.startsWith('btx-private-')).forEach(key => sessionStorage.removeItem(key)); window.location.reload() })} />
    ) : surface === 'monitor' ? (
      navigationAuthority.sourceHealth ? <Monitor
        health={monitor}
        settings={workspaceSettings}
        onIntelligence={() => {
          clearSelectedEvent()
          clearMapSelection()
          clearSelectedAction()
          clearViewContext()
          navigate('intelligence')
        }}
      /> : <section className="surface" role="status">Checking workspace access…</section>
    ) : (
      <Today
        filters={todayFilters}
        onFilters={setTodayFilters}
        commandCenter={commandCenter}
        state={todayState}
        alerts={alerts}
        signals={signals}
        accounts={accounts}
        onAccount={(id, assessment) => void select(id, true, assessment)}
        onIntelligence={() => navigate('intelligence')}
        onSourceHealth={navigationAuthority.sourceHealth ? () => navigate('monitor') : undefined}
        onEventSelect={setSelectedEventId}
        onAction={(alert) => {
          clearSelectedEvent()
          clearMapSelection()
          clearSelectedAction()
          clearViewContext()
          navigate('actions')
          setActionSourceAlertId(alert.id)
          setError('')
        }}
        onOmniContext={setViewContext}
        location={location}
        onLocationChange={commitLocation}
      />
    )
  const omniSurface: OmniSurface =
    detail && surface === 'accounts'
      ? 'ACCOUNT_DETAIL'
      : (
          {
            today: 'TODAY',
            accounts: 'ACCOUNTS',
            intelligence: 'INTELLIGENCE',
            map: 'MAP',
            actions: 'ACTIONS',
            communications: 'COMMUNICATIONS',
            settings: 'SETTINGS',
            monitor: 'MONITOR',
          } as const
        )[surface]
  const filteredAccountId = typeof viewContext.active_filters?.account_id === 'string'
    ? viewContext.active_filters.account_id
    : undefined
  const selectedAccountId = detail?.account.id ?? (surface === 'map' ? selectedMapAccountId : filteredAccountId)
  const omniContext: OmniContext = {
    surface: omniSurface,
    selected_account_id: selectedAccountId,
    selected_event_id: surface === 'intelligence' || surface === 'today' || surface === 'map' || (surface === 'accounts' && detail) ? (viewContext.selected_assessment?.event_id ?? selectedEventId ?? viewContext.selected_event_id) : undefined,
    selected_assessment: viewContext.selected_assessment,
    selected_federal_opportunity: viewContext.selected_federal_opportunity,
    selected_program_id: surface === 'today' ? viewContext.selected_program_id : undefined,
    // A facility-supported map investigation remains scoped to that facility
    // after the user opens Organization 360.  The URL never promotes an
    // account-wide assessment to facility evidence; it only preserves the
    // already selected canonical site for Omni's supporting context.
    selected_facility_id: surface === 'map' ? selectedMapFacilityId : surface === 'accounts' ? location.facilityId : undefined,
    selected_action_id: surface === 'actions' ? selectedActionId : undefined,
    relationship_selection: omniSurface === 'ACCOUNT_DETAIL' ? viewContext.relationship_selection : undefined,
    active_filters: omniSurface === 'ACCOUNT_DETAIL' ? undefined : viewContext.active_filters,
    visible_record_ids: omniSurface === 'ACCOUNT_DETAIL' ? undefined : viewContext.visible_record_ids,
  }
  const selectedAccount = accounts.find((account) => account.id === selectedAccountId)
  return (
    <main className="app-shell">
      <aside className="app-sidebar">
        <button className="wordmark" onClick={() => navigate('today')} aria-label="Go to Today">
          BTX <span>OMNI</span>
          <small>Commercial intelligence</small>
        </button>
        <nav className="sidebar-nav" aria-label="Primary navigation">
          {desktopPrimaryDestinations.map(destination => (
            <button key={destination.surface} className={surface === destination.surface ? 'active' : ''} aria-current={surface === destination.surface ? 'page' : undefined} title={destination.job} onClick={() => navigate(destination.surface)}>
              {destination.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          {desktopSecondaryDestinations.map(destination => <button key={destination.surface} className={surface === destination.surface ? 'active' : ''} aria-current={surface === destination.surface ? 'page' : undefined} title={destination.job} onClick={() => navigate(destination.surface)}>{destination.label}</button>)}
          <span className="eyebrow">{actionPrincipal?.display_name ?? 'Governed seller workspace'}</span>
          <small>{actionPrincipal?.role ?? 'Public evidence + SAMPLE context'}</small>
        </div>
      </aside>
      <section className="app-workspace">
        <header className="topbar">
          <div className="topbar-context">
            <span className="eyebrow">BTX Omni Prospect</span>
            <strong>{surfaceLabels[surface]}</strong>
          </div>
          <div className="topbar-controls">
          {actionPrincipal && <div className="signed-in-user" aria-label="Signed-in user"><span aria-hidden="true">{actionPrincipal.display_name.split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase()}</span><strong>{actionPrincipal.display_name}</strong></div>}
          <Disclosure className="mode" title="Workspace menu" open={workspaceMenuOpen} onOpenChange={setWorkspaceMenuOpen}>
            <div className="mobile-secondary-links">
              {mobileSecondaryDestinations.map(destination => <button key={destination.surface} aria-current={surface === destination.surface ? 'page' : undefined} onClick={() => navigate(destination.surface)}>{destination.label}</button>)}
            </div>
            <p>Public evidence and SAMPLE commercial context remain explicitly separated.</p>
            {actionPrincipal && <p className="mobile-user-identity">Signed in as {actionPrincipal.display_name}</p>}
          </Disclosure>
          </div>
        </header>
        <aside className="demonstration-banner" aria-label="Demonstration environment">Simulated data environment</aside>
        {linkRecovery && <div className="api-notice" role="alert">{linkRecovery} <button type="button" onClick={() => navigate(surface)}>Return to {surfaceLabels[surface]}</button></div>}
        {error && <div className="api-notice">{error}</div>}
        {accountOpening && <div className="api-notice" role="status">Opening {accounts.find(account => account.id === accountOpening)?.name ?? 'account'}… <button type="button" onClick={() => { accountRequest.current?.abort(); setAccountOpening(undefined) }}>Cancel</button></div>}
        {surface !== 'settings' && resourceState[surface] === 'error' && <StatusMessage state="error" title={`${surfaceLabels[surface]} could not refresh`} action={<Button onClick={() => setResourceRefresh(previous => ({ key: surface, version: (previous?.version ?? 0) + 1 }))}>Retry {surfaceLabels[surface]}</Button>}>{resourceReady[surface] ? 'Last-good content remains visible and is not labeled as freshly collected.' : 'This resource is unavailable. Other permitted workspace sections remain available.'}</StatusMessage>}
        {surface === 'settings' ? content : !resourceState[surface] ? <section className="surface"><StatusMessage state="loading" title={`Loading ${surfaceLabels[surface]}`}>Other workspace sections remain available.</StatusMessage></section> : resourceReady[surface] ? content : null}
      </section>
      <nav className="mobile-primary-nav" aria-label="Mobile primary navigation">
        {mobilePrimaryDestinations.map(destination => (
          <button key={destination.surface} className={surface === destination.surface ? 'active' : ''} aria-current={surface === destination.surface ? 'page' : undefined} onClick={() => navigate(destination.surface)}>
            {destination.label}
          </button>
        ))}
      </nav>
      <OmniDrawer accountId={selectedAccountId} accountName={detail?.account.name ?? detail?.account.legal_name ?? selectedAccount?.name ?? selectedAccount?.legal_name} context={omniContext} />
    </main>
  )
}

function HostedSignIn({ onAuthenticated }: { onAuthenticated: () => void }) {
  const [accessCode, setAccessCode] = useState(''); const [error, setError] = useState(''); const [submitting, setSubmitting] = useState(false)
  const submit = async (event: React.FormEvent) => { event.preventDefault(); setSubmitting(true); setError(''); try { await api.signIn(accessCode); setAccessCode(''); onAuthenticated() } catch { setError('The hosted access code is invalid or session authentication is not configured.') } finally { setSubmitting(false) } }
  return <main className="app-shell app-shell-loading"><form className="loading-stage" onSubmit={event => void submit(event)}><span className="eyebrow">Hosted POC access</span><h1>Sign in to Omni Prospect</h1><p>Enter an administrator-issued short-lived POC access code. The code is exchanged server-side and is never stored in the frontend.</p><label>Access code<input type="password" autoComplete="current-password" value={accessCode} onChange={event => setAccessCode(event.target.value)} required /></label>{error && <p role="alert">{error}</p>}<button type="submit" disabled={submitting}>{submitting ? 'Signing in…' : 'Sign in'}</button></form></main>
}
