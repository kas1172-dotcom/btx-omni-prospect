import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { OmniDrawer } from '../components/OmniDrawer'
import { Actions } from '../features/actions/Actions'
import { Accounts } from '../features/accounts/Accounts'
import { Intelligence } from '../features/intelligence/Intelligence'
import { Map } from '../features/map/Map'
import { Today } from '../features/today/Today'
import type { Account, Account360, Alert, MapRecord, Signal, WorkItem } from '../types/api'
import '../design/tokens.css'
import '../design/app.css'
import '../design/mobile.css'

type Surface = 'today' | 'accounts' | 'intelligence' | 'map' | 'actions'
const nav: Array<[Surface, string]> = [['today', 'Today'], ['accounts', 'Accounts'], ['intelligence', 'Intelligence'], ['map', 'Map'], ['actions', 'Actions']]

export default function App() {
  const [surface, setSurface] = useState<Surface>('today')
  const [accounts, setAccounts] = useState<Account[]>([]); const [alerts, setAlerts] = useState<Alert[]>([]); const [signals, setSignals] = useState<Signal[]>([])
  const [records, setRecords] = useState<MapRecord[]>([]); const [mapSignals, setMapSignals] = useState<Signal[]>([]); const [layers, setLayers] = useState<string[]>([])
  const [detail, setDetail] = useState<Account360>(); const [items, setItems] = useState<WorkItem[]>([]); const [error, setError] = useState(''); const [loading, setLoading] = useState(true)
  const select = async (id: string) => { try { setError(''); setDetail(await api.account(id)); setSurface('accounts') } catch (error) { setError(error instanceof Error ? error.message : 'Account context unavailable.') } }
  useEffect(() => { void Promise.all([api.accounts(), api.today(), api.intelligence(), api.map()]).then(([accountData, today, intelligence, map]) => { setAccounts(accountData.accounts); setAlerts(today.commercial_alerts); setSignals(intelligence.signals); setRecords(map.records); setMapSignals(map.intelligence_signals); setLayers(map.layers) }).catch(error => setError(error instanceof Error ? error.message : 'Canonical API unavailable.')).finally(() => setLoading(false)) }, [])
  const content = () => { if (loading) return <div className="loading-stage"><span className="eyebrow">Loading governed context</span><h1>Preparing Omni Prospect</h1><p>Resolving canonical account, commercial, intelligence, and map context.</p></div>; if (surface === 'accounts') return <Accounts accounts={accounts} detail={detail} onSelect={id => void select(id)} />; if (surface === 'intelligence') return <Intelligence signals={signals} onAccount={id => void select(id)} />; if (surface === 'map') return <Map records={records} layers={layers} signals={mapSignals} onAccount={id => void select(id)} />; if (surface === 'actions') return <Actions items={items} onItem={item => setItems(old => [...old.filter(value => value.id !== item.id), item])} alerts={alerts} />; return <Today alerts={alerts} signals={signals} onAccount={id => void select(id)} onAction={alert => { setSurface('actions'); setError(`Ready to create action for ${alert.account_id}.`) }} /> }
  return <main className="app-shell"><header className="topbar"><button className="wordmark" onClick={() => setSurface('today')}>BTX <span>OMNI</span></button><span className="mode">SAMPLE INTERNAL · LIVE PUBLIC</span><nav aria-label="Primary navigation">{nav.map(([id, label]) => <button key={id} className={surface === id ? 'active' : ''} onClick={() => setSurface(id)}>{label}</button>)}</nav></header>{error && <div className="api-notice">{error}</div>}{content()}<OmniDrawer accountId={detail?.account.id} surface={surface} /></main>
}
