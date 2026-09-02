import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import { OmniDrawer } from '../components/OmniDrawer'
import { Disclosure } from '../components/UI'
import { Actions } from '../features/actions/Actions'
import { Communications } from '../features/communications/Communications'
import { Accounts } from '../features/accounts/Accounts'
import { Intelligence } from '../features/intelligence/Intelligence'
import { Map } from '../features/map/Map'
import { Monitor } from '../features/monitor/Monitor'
import { Today } from '../features/today/Today'
import { Settings } from '../features/settings/Settings'
import type { Account, Account360, Alert, BtxMapFacility, CommandCenter, CommunicationDraft, MapIntelligence, MapRecord, MonitorHealth, OmniContext, OmniSurface, Principal, PublicLocation, Signal, Suggestion, WorkItem, WorkspaceSettings } from '../types/api'
import '../design/tokens.css'
import '../design/app.css'
import '../design/shell.css'
import '../design/mobile.css'
type Surface = 'today' | 'accounts' | 'intelligence' | 'map' | 'actions' | 'communications' | 'settings' | 'monitor'
type OmniViewContext = Pick<OmniContext, 'selected_event_id' | 'selected_program_id' | 'active_filters' | 'visible_record_ids'>
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
  const [surface, setSurface] = useState<Surface>('today')
  const [accounts, setAccounts] = useState<Account[]>([])
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [signals, setSignals] = useState<Signal[]>([])
  const [records, setRecords] = useState<MapRecord[]>([])
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
  const [loading, setLoading] = useState(true)
  const [selectedEventId, setSelectedEventId] = useState<string>()
  const [selectedMapAccountId, setSelectedMapAccountId] = useState<string>()
  const [selectedMapFacilityId, setSelectedMapFacilityId] = useState<string>()
  const [selectedActionId, setSelectedActionId] = useState<string>()
  const [viewContext, setViewContext] = useState<OmniViewContext>({})
  const clearSelectedEvent = useCallback(() => setSelectedEventId(undefined), [])
  const clearMapSelection = useCallback(() => {
    setSelectedMapAccountId(undefined)
    setSelectedMapFacilityId(undefined)
  }, [])
  const clearSelectedAction = useCallback(() => setSelectedActionId(undefined), [])
  const clearViewContext = useCallback(() => setViewContext({}), [])
  const select = async (id: string) => {
    try {
      setError('')
      clearSelectedEvent()
      clearMapSelection()
      clearSelectedAction()
      clearViewContext()
      setDetail(await api.account(id))
      setSurface('accounts')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Customer context unavailable.')
    }
  }
  const navigate = (id: Surface) => {
    if (id !== surface || (id === 'accounts' && detail)) {
      clearSelectedEvent()
      clearMapSelection()
      clearSelectedAction()
      clearViewContext()
      setDetail(undefined)
    }
    setSurface(id)
  }
  useEffect(() => { if (import.meta.env.DEV) return; void api.session().then(() => setAuthState('authenticated')).catch(() => setAuthState('required')) }, [])
  useEffect(() => {
    if (authState !== 'authenticated') return
    void Promise.allSettled([api.accounts(), api.today(), api.intelligence(), api.map(), api.actions(), api.communications(), api.settings()])
      .then(([accountsResult, todayResult, intelligenceResult, mapResult, actionResult, communicationResult, settingsResult]) => {
        if (accountsResult.status === 'fulfilled') setAccounts(accountsResult.value.accounts)
        else setError('Core workspace catalog is unavailable.')
        if (todayResult.status === 'fulfilled') {
          setAlerts(todayResult.value.commercial_alerts)
          setCommandCenter(todayResult.value.command_center)
          setTodayState('loaded')
        } else setTodayState('unavailable')
        if (intelligenceResult.status === 'fulfilled') setSignals(intelligenceResult.value.signals)
        if (mapResult.status === 'fulfilled') {
          setRecords(mapResult.value.accounts)
          setPublicLocations(mapResult.value.facilities)
          setBtxFacilities(mapResult.value.btx_facilities)
          setMapSignals(mapResult.value.intelligence)
          setLayers(mapResult.value.layers)
        }
        if (actionResult.status === 'fulfilled') {
          setItems(actionResult.value.items)
          setSuggestions(actionResult.value.suggestions)
          setActionPrincipal(actionResult.value.principal)
          setActionWarning(actionResult.value.warning)
        }
        if (communicationResult.status === 'fulfilled') setCommunications(communicationResult.value.items)
        if (settingsResult.status === 'fulfilled') { setWorkspaceSettings(settingsResult.value); setSettingsState('loaded') }
        else setSettingsState('error')
      })
      .finally(() => setLoading(false))
    void api
      .monitor()
      .then(setMonitor)
      .catch(() => setMonitor(undefined))
  }, [authState])
  if (authState === 'checking') return <main className="app-shell app-shell-loading"><div className="loading-stage"><span className="eyebrow">Secure workspace</span><h1>Checking hosted session</h1><p>Validating the server-held POC session without exposing role credentials.</p></div></main>
  if (authState === 'required') return <HostedSignIn onAuthenticated={() => window.location.reload()} />
  if (loading)
    return (
      <main className="app-shell app-shell-loading">
        <div className="loading-stage">
          <span className="eyebrow">Loading governed context</span>
          <h1>Preparing Omni Prospect</h1>
          <p>Resolving public evidence and simulated POC context.</p>
        </div>
      </main>
    )
  const content =
    surface === 'accounts' ? (
      <Accounts accounts={accounts} detail={detail} onSelect={(id) => void select(id)} onBack={() => navigate('accounts')} onOmniContext={setViewContext} />
    ) : surface === 'intelligence' ? (
      <Intelligence signals={signals} accounts={accounts} commandCenter={commandCenter} monitor={monitor} settings={workspaceSettings} onAccount={(id) => void select(id)} onEventSelect={setSelectedEventId} onCreateAction={(brief) => { clearSelectedEvent(); clearMapSelection(); clearSelectedAction(); clearViewContext(); setSurface('actions'); setError(`Create an internal Action for ${accounts.find(account => account.id === brief.canonical_account_ids[0])?.name ?? 'the linked Customer'} using the governed next step.`) }} onOmniContext={setViewContext} />
    ) : surface === 'map' ? (
      <Map
        records={records}
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
        onMapFacilitySelect={(facilityId, accountId) => {
          setSelectedMapFacilityId(facilityId)
          setSelectedMapAccountId(accountId)
        }}
        onMapEventSelect={setSelectedEventId}
        onOmniContext={setViewContext}
      />
    ) : surface === 'actions' ? (
      <Actions items={items} suggestions={suggestions} principal={actionPrincipal} onItem={(item) => setItems((old) => [...old.filter((value) => value.id !== item.id), item])} onSuggestions={setSuggestions} accounts={accounts} signals={signals} warning={actionWarning} onAccount={(id) => void select(id)} onActionSelect={setSelectedActionId} onOmniContext={setViewContext} />
    ) : surface === 'communications' ? (
      <Communications accounts={accounts} principal={actionPrincipal} items={communications} onItem={(item) => setCommunications((old) => [...old.filter((value) => value.id !== item.id), item])} onAccount={(id) => void select(id)} />
    ) : surface === 'settings' ? (
      <Settings settings={workspaceSettings} state={settingsState} onSettings={setWorkspaceSettings} onRetry={() => { setSettingsState('loading'); void api.settings().then(value => { setWorkspaceSettings(value); setSettingsState('loaded') }).catch(() => setSettingsState('error')) }} onSignOut={() => void api.signOut().then(() => window.location.reload())} />
    ) : surface === 'monitor' ? (
      <Monitor
        health={monitor}
        onAccount={(id) => void select(id)}
        onIntelligence={() => {
          clearSelectedEvent()
          clearMapSelection()
          clearSelectedAction()
          clearViewContext()
          setSurface('intelligence')
        }}
      />
    ) : (
      <Today
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
          setSurface('actions')
          setError(`Ready to create action for ${accounts.find((account) => account.id === alert.account_id)?.name ?? 'selected Customer'}.`)
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
          <Disclosure className="mode" title="Workspace menu">
            <div className="mobile-secondary-links">
              <button onClick={() => navigate('communications')}>Communications</button>
              <button onClick={() => navigate('settings')}>Settings</button>
            </div>
            <p>Public evidence and SAMPLE commercial context remain explicitly separated.</p>
          </Disclosure>
        </header>
        {error && <div className="api-notice">{error}</div>}
        {content}
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
