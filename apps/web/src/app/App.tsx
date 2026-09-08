import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { OmniDrawer } from '../components/OmniDrawer'
import { Disclosure } from '../components/UI'
import { deferredSurface } from '../components/deferredSurface'
import type { PortfolioSnapshot } from '../features/accounts/Accounts'
import { Today, type TodayFilters } from '../features/today/Today'
import { workspaceHash, workspaceLocation, type Surface } from './navigation'
import type { Account, Account360, Alert, BtxMapFacility, CommandCenter, CommunicationDraft, MapIntelligence, MapRecord, MonitorHealth, OmniContext, OmniSurface, Principal, PublicLocation, Signal, Suggestion, WorkItem, WorkspaceSettings } from '../types/api'
import '../design/tokens.css'
import '../design/app.css'
import '../design/shell.css'
import '../design/mobile.css'
const Accounts = deferredSurface(() => import('../features/accounts/Accounts').then(module => module.Accounts), 'Customers & Prospects', 'Accounts')
const Map = deferredSurface(() => import('../features/map/Map').then(module => module.Map), 'Map', 'Map')
const Actions = deferredSurface(() => import('../features/actions/Actions').then(module => module.Actions), 'Actions', 'Actions')
const Communications = deferredSurface(() => import('../features/communications/Communications').then(module => module.Communications), 'Communications', 'Communications')
const Intelligence = deferredSurface(() => import('../features/intelligence/Intelligence').then(module => module.Intelligence), 'Intelligence', 'Intelligence')
const Monitor = deferredSurface(() => import('../features/monitor/Monitor').then(module => module.Monitor), 'Monitor', 'Monitor')
const Settings = deferredSurface(() => import('../features/settings/Settings').then(module => module.Settings), 'Settings', 'Settings')
type OmniViewContext = Pick<OmniContext, 'selected_event_id' | 'selected_program_id' | 'active_filters' | 'visible_record_ids' | 'relationship_selection'>
const nav: Array<[Surface, string]> = [
  ['today', 'Today'],
  ['accounts', 'Customers & Prospects'],
  ['intelligence', 'Intelligence'],
  ['map', 'Map'],
  ['actions', 'Actions'],
  ['communications', 'Communications'],
  ['monitor', 'Monitor'],
]
const mobileNav = nav.filter(([id]) => ['today', 'accounts', 'intelligence', 'map', 'actions'].includes(id))
const surfaceLabels: Record<Surface, string> = {
  today: 'Today',
  accounts: 'Customers & Prospects',
  intelligence: 'Intelligence',
  map: 'Map',
  actions: 'Actions',
  communications: 'Communications',
  settings: 'Settings',
  monitor: 'Monitor',
}
export default function App() {
  const [authState, setAuthState] = useState<'checking' | 'authenticated' | 'required'>(import.meta.env.DEV ? 'authenticated' : 'checking')
  const [commandCenter, setCommandCenter] = useState<CommandCenter>()
  const [todayState, setTodayState] = useState<'loading' | 'loaded' | 'unavailable'>('loading')
  const [todayFilters, setTodayFilters] = useState<TodayFilters>({ kind: 'ALL', accountId: '', businessUnit: '' })
  const [surface, setSurface] = useState<Surface>(() => workspaceLocation(window.location.hash).surface)
  const [workspaceMenuOpen, setWorkspaceMenuOpen] = useState(false)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [portfolioSnapshot, setPortfolioSnapshot] = useState<PortfolioSnapshot>()
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [signals, setSignals] = useState<Signal[]>([])
  const [records, setRecords] = useState<MapRecord[]>([])
  const [pendingMapAccounts, setPendingMapAccounts] = useState<import('../types/api').PendingMapAccount[]>([])
  const [mapViewSnapshot, setMapViewSnapshot] = useState<import('../features/map/mapModel').MapViewSnapshot>()
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
  const [error, setError] = useState('')
  const [resourceState, setResourceState] = useState<Partial<Record<Surface, 'loading' | 'loaded' | 'error'>>>({})
  const [resourceReady, setResourceReady] = useState<Partial<Record<Surface, boolean>>>({})
  const [refreshVersion, setRefreshVersion] = useState(0)
  const [accountOpening, setAccountOpening] = useState<string>()
  const accountRequest = useRef<AbortController | undefined>(undefined)
  const [selectedEventId, setSelectedEventId] = useState<string>()
  const [selectedMapAccountId, setSelectedMapAccountId] = useState<string>()
  const [selectedMapFacilityId, setSelectedMapFacilityId] = useState<string>()
  const [selectedActionId, setSelectedActionId] = useState<string>()
  const [actionSourceAlertId, setActionSourceAlertId] = useState<string>()
  const [viewContext, setViewContext] = useState<OmniViewContext>({})
  const clearSelectedEvent = useCallback(() => setSelectedEventId(undefined), [])
  const clearMapSelection = useCallback(() => {
    setSelectedMapAccountId(undefined)
    setSelectedMapFacilityId(undefined)
  }, [])
  const clearSelectedAction = useCallback(() => { setSelectedActionId(undefined); setActionSourceAlertId(undefined) }, [])
  const clearViewContext = useCallback(() => setViewContext({}), [])
  const selectMapFacility = useCallback((facilityId?: string, accountId?: string) => { setSelectedMapFacilityId(facilityId); setSelectedMapAccountId(accountId) }, [])
  const select = useCallback(async (id: string, recordHistory = true) => {
    accountRequest.current?.abort()
    const controller = new AbortController(); accountRequest.current = controller
    setAccountOpening(id)
    try {
      setError('')
      const result = await api.account(id, controller.signal)
      if (controller.signal.aborted) return
      clearSelectedEvent()
      clearMapSelection()
      clearSelectedAction()
      clearViewContext()
      setDetail(result)
      setSurface('accounts')
      if (recordHistory && window.location.hash !== workspaceHash('accounts', id)) window.history.pushState({ btxOmniNavigation: true }, '', workspaceHash('accounts', id))
    } catch (err) {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Customer context unavailable.')
    } finally { if (accountRequest.current === controller) setAccountOpening(undefined) }
  }, [clearSelectedEvent, clearMapSelection, clearSelectedAction, clearViewContext])
  const navigate = useCallback((id: Surface, recordHistory = true) => {
    accountRequest.current?.abort(); setAccountOpening(undefined)
    setWorkspaceMenuOpen(false)
    if (id !== surface || (id === 'accounts' && detail)) {
      clearSelectedEvent()
      clearMapSelection()
      clearSelectedAction()
      clearViewContext()
      setDetail(undefined)
    }
    setSurface(id)
    if (recordHistory && window.location.hash !== workspaceHash(id)) window.history.pushState({ btxOmniNavigation: true }, '', workspaceHash(id))
  }, [surface, detail, clearSelectedEvent, clearMapSelection, clearSelectedAction, clearViewContext])
  useEffect(() => {
    if (authState !== 'authenticated') return
    const restore = () => { const location = workspaceLocation(window.location.hash); if (location.accountId) void select(location.accountId, false); else navigate(location.surface, false) }
    window.addEventListener('hashchange', restore)
    return () => window.removeEventListener('hashchange', restore)
  }, [authState, select, navigate])
  useEffect(() => {
    if (authState !== 'authenticated') return
    const location = workspaceLocation(window.location.hash)
    if (!location.accountId) return
    const controller = new AbortController(); accountRequest.current = controller
    void api.account(location.accountId, controller.signal).then(result => {
      if (!controller.signal.aborted) { setDetail(result); setSurface('accounts') }
    }).catch(err => {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Customer context unavailable.')
    })
    return () => controller.abort()
  }, [authState])
  useEffect(() => { if (import.meta.env.DEV) return; void api.session().then(() => setAuthState('authenticated')).catch(() => setAuthState('required')) }, [])
  useEffect(() => {
    if (authState !== 'authenticated') return
    const controller = new AbortController(); const { signal } = controller
    // Publish each independent read as it arrives. A slow optional surface must
    // not hold the entire workspace behind an all-settled loading screen.
    const load = <T,>(key: Surface, promise: Promise<T>, publish: (value: T) => void, failed?: () => void) => {
      void promise.then(value => { if (!signal.aborted) { publish(value); setResourceReady(old => ({ ...old, [key]: true })); setResourceState(old => ({ ...old, [key]: 'loaded' })) } }).catch(() => { if (!signal.aborted) { failed?.(); setResourceState(old => ({ ...old, [key]: 'error' })) } })
    }
    load('accounts', api.accounts(signal), value => setAccounts(value.accounts))
    load('today', api.today(signal), value => { setAlerts(value.commercial_alerts); setCommandCenter(value.command_center); setTodayState('loaded') }, () => setTodayState('unavailable'))
    load('intelligence', api.intelligence(signal), value => setSignals(value.signals))
    load('map', api.map(undefined, signal), value => { setRecords(value.accounts); setPendingMapAccounts(value.pending_accounts ?? []); setPublicLocations(value.facilities); setBtxFacilities(value.btx_facilities); setMapSignals(value.intelligence); setLayers(value.layers) })
    load('actions', api.actions(signal), value => { setItems(value.items); setSuggestions(value.suggestions); setActionPrincipal(value.principal); setActionWarning(value.warning) })
    load('communications', api.communications(signal), value => setCommunications(value.items))
    load('settings', api.settings(signal), value => { setWorkspaceSettings(value); setSettingsState('loaded') }, () => setSettingsState('error'))
    load('monitor', api.monitor(signal), setMonitor)
    return () => controller.abort()
  }, [authState, refreshVersion])
  useEffect(() => () => accountRequest.current?.abort(), [])
  if (authState === 'checking') return <main className="app-shell app-shell-loading"><div className="loading-stage"><span className="eyebrow">Secure workspace</span><h1>Checking hosted session</h1><p>Validating the server-held POC session without exposing role credentials.</p></div></main>
  if (authState === 'required') return <HostedSignIn onAuthenticated={() => window.location.reload()} />
  const content =
    surface === 'accounts' ? (
      <Accounts accounts={accounts} detail={detail} initialSnapshot={portfolioSnapshot} onSnapshot={setPortfolioSnapshot} onSelect={(id) => void select(id)} onBack={() => navigate('accounts')} onOmniContext={setViewContext} />
    ) : surface === 'intelligence' ? (
      <Intelligence signals={signals} accounts={accounts} commandCenter={commandCenter} monitor={monitor} settings={workspaceSettings} onAccount={(id) => void select(id)} onEventSelect={setSelectedEventId} onCreateAction={(brief) => { navigate('actions'); setError(`Create an internal Action for ${accounts.find(account => account.id === brief.canonical_account_ids[0])?.name ?? 'the linked Customer'} using the governed next step.`) }} onOmniContext={setViewContext} />
    ) : surface === 'map' ? (
      <Map
        records={records}
        pendingAccounts={pendingMapAccounts}
        initialSnapshot={mapViewSnapshot}
        onSnapshot={setMapViewSnapshot}
        publicLocations={publicLocations}
        btxFacilities={btxFacilities}
        layers={layers}
        signals={mapSignals}
        onAccount={(id) => void select(id)}
        onRelationships={(id) => void select(id)}
        onMapAccountSelect={(id) => {
          setSelectedMapAccountId(id)
          setSelectedMapFacilityId(undefined)
        }}
        onMapFacilitySelect={selectMapFacility}
        onMapEventSelect={setSelectedEventId}
        onOmniContext={setViewContext}
      />
    ) : surface === 'actions' ? (
      <Actions items={items} suggestions={suggestions} principal={actionPrincipal} onItem={(item) => setItems((old) => [...old.filter((value) => value.id !== item.id), item])} onSuggestions={setSuggestions} accounts={accounts} signals={signals} warning={actionWarning} onAccount={(id) => void select(id)} onActionSelect={setSelectedActionId} onOmniContext={setViewContext} sourceAlertId={actionSourceAlertId} onClearSource={() => setActionSourceAlertId(undefined)} />
    ) : surface === 'communications' ? (
      <Communications accounts={accounts} principal={actionPrincipal} items={communications} onItem={(item) => setCommunications((old) => [...old.filter((value) => value.id !== item.id), item])} onAccount={(id) => void select(id)} />
    ) : surface === 'settings' ? (
      <Settings accounts={accounts} settings={workspaceSettings} state={settingsState} onSettings={setWorkspaceSettings} onRetry={() => { setSettingsState('loading'); void api.settings().then(value => { setWorkspaceSettings(value); setSettingsState('loaded'); setResourceReady(previous => ({ ...previous, settings: true })); setResourceState(previous => ({ ...previous, settings: 'loaded' })) }).catch(() => setSettingsState('error')) }} onSignOut={() => void api.signOut().then(() => window.location.reload())} />
    ) : surface === 'monitor' ? (
      <Monitor
        health={monitor}
        onAccount={(id) => void select(id)}
        onIntelligence={() => {
          clearSelectedEvent()
          clearMapSelection()
          clearSelectedAction()
          clearViewContext()
          navigate('intelligence')
        }}
      />
    ) : (
      <Today
        filters={todayFilters}
        onFilters={setTodayFilters}
        commandCenter={commandCenter}
        state={todayState}
        alerts={alerts}
        signals={signals}
        accounts={accounts}
        onAccount={(id) => void select(id)}
        onIntelligence={() => navigate('intelligence')}
        onMonitor={() => navigate('monitor')}
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
  const selectedAccountId = detail?.account.id ?? (surface === 'map' ? selectedMapAccountId : undefined)
  const omniContext: OmniContext = {
    surface: omniSurface,
    selected_account_id: selectedAccountId,
    selected_event_id: surface === 'intelligence' || surface === 'today' || surface === 'map' ? (selectedEventId ?? viewContext.selected_event_id) : undefined,
    selected_program_id: surface === 'today' ? viewContext.selected_program_id : undefined,
    selected_facility_id: surface === 'map' ? selectedMapFacilityId : undefined,
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
          {nav.map(([id, label]) => (
            <button key={id} className={surface === id ? 'active' : ''} aria-current={surface === id ? 'page' : undefined} onClick={() => navigate(id)}>
              {label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <button className={surface === 'settings' ? 'active' : ''} onClick={() => navigate('settings')}>
            Settings
          </button>
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
              <button onClick={() => navigate('communications')}>Communications</button>
              <button onClick={() => navigate('settings')}>Settings</button>
            </div>
            <p>Public evidence and SAMPLE commercial context remain explicitly separated.</p>
            {actionPrincipal && <p className="mobile-user-identity">Signed in as {actionPrincipal.display_name}</p>}
          </Disclosure>
          </div>
        </header>
        <aside className="demonstration-banner" aria-label="Demonstration environment">Simulated data environment</aside>
        {error && <div className="api-notice">{error}</div>}
        {accountOpening && <div className="api-notice" role="status">Opening {accounts.find(account => account.id === accountOpening)?.name ?? 'account'}… <button type="button" onClick={() => { accountRequest.current?.abort(); setAccountOpening(undefined) }}>Cancel</button></div>}
        {surface !== 'settings' && resourceState[surface] === 'error' && <div className="api-notice" role="alert">{surfaceLabels[surface]} could not refresh. Previously loaded content is retained, if available. <button type="button" onClick={() => setRefreshVersion(version => version + 1)}>Retry workspace reads</button></div>}
        {surface === 'settings' ? content : !resourceState[surface] ? <section className="surface" role="status">Loading {surfaceLabels[surface]}… Other workspace sections remain available.</section> : resourceReady[surface] ? content : null}
      </section>
      <nav className="mobile-primary-nav" aria-label="Mobile primary navigation">
        {mobileNav.map(([id, label]) => (
          <button key={id} className={surface === id ? 'active' : ''} aria-current={surface === id ? 'page' : undefined} onClick={() => navigate(id)}>
            {label}
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
