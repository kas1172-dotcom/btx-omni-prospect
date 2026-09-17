import type { MonitorHealth, WorkspaceSettings } from '../../types/api'
import { Button, Disclosure, Empty, Panel, StatusBadge } from '../../components/UI'
import { CanonicalRecord } from '../../components/CanonicalRecord'
import { EvidencePassages } from '../../components/EvidencePassages'
import { presentationLabel } from '../../components/presentation'
import './monitor.css'

const utcDateTime = (value?: string) => value
  ? new Date(value).toLocaleString('en-US', { timeZone: 'UTC', dateStyle: 'medium', timeStyle: 'short' }) + ' UTC'
  : 'Unavailable'

const schedulerLabel = (state: string) => ({
  SCHEDULE_NOT_CONFIRMED: 'Schedule not confirmed',
  SCHEDULE_CONFIGURED_AWAITING_RUN: 'Awaiting first scheduled run',
  LATEST_SCHEDULED_RUN_FAILED: 'Latest scheduled run failed',
  COLLECTION_OBSERVED_STALE: 'Collection is stale',
  COLLECTION_OBSERVED_CURRENT: 'Collection is current',
})[state] ?? 'Schedule state unavailable'

const sourceState = (state?: string) => ({
  HEALTHY: 'Connected',
  CONNECTED: 'Connected',
  CURRENT: 'Connected',
  PARTIAL: 'Partial coverage',
  STALE: 'Stale',
  UNAVAILABLE: 'Unavailable',
  NOT_CONFIGURED: 'Unavailable',
  NEVER_ATTEMPTED: 'Awaiting first check',
  PERMISSION_LIMITED: 'Permission limited',
  FAILED: 'Action required',
  RATE_LIMITED: 'Partial coverage',
  WORKER_RUNTIME_NOT_CONFIGURED: 'Worker not configured',
  WORKER_READY_FOR_INVOCATION: 'Worker ready for scheduled invocation',
})[state ?? ''] ?? presentationLabel(state ?? 'UNAVAILABLE', 'provider')

const integrationNames: Record<string, string> = { google_maps: 'Google Maps', gemini: 'Gemini', hubspot: 'CRM', communications: 'Communication delivery', prism: 'Commercial data boundary', sam_gov: 'SAM.gov', usaspending: 'USAspending' }

const blockingFailures = (failures?: string[]) => (failures ?? []).filter(item => !item.startsWith('AWAITING_CONTINUATION:'))

export function Monitor({ health, settings, onIntelligence }: { health?: MonitorHealth; settings?: WorkspaceSettings; onIntelligence: () => void }) {
  if (!health) return <div className="surface monitor-surface"><header className="page-title monitor-title"><span className="eyebrow">Administrator operations</span><h1>Source Health</h1></header><Empty>Source Health is unavailable. No provider success is implied.</Empty></div>

  const latestRun = health.last_runs[0]
  const lastSuccessfulRun = health.last_runs.find(run => run.completed_at && blockingFailures(run.failures).length === 0)
  const coverage = health.federal_procurement_coverage ?? []
  const pendingCoverage = coverage.filter(item => item.pending_continuation)
  const completeCoverage = coverage.filter(item => !item.pending_continuation && item.coverage_state === 'COMPLETE')
  const currentEvents = (health.events ?? []).filter(event => event.is_current_source_version !== false)
  const accepted = currentEvents.filter(event => event.seller_relevance_state === 'RESOLVED_ELIGIBLE').length
  const reviewRequired = currentEvents.filter(event => event.resolution_state.includes('NEEDS_REVIEW') || event.seller_relevance_state?.includes('REVIEW')).length
  const persisted = health.persisted_assessments
  const operatorAction = blockingFailures(latestRun?.failures).length
    ? 'Review the failed source detail, correct the reported condition, and retry through the authorized worker.'
    : pendingCoverage.length
      ? 'Allow the configured worker to continue from its saved checkpoints; partial coverage is not a total market count.'
      : health.scheduler_state === 'COLLECTION_OBSERVED_STALE'
        ? 'Confirm the scheduler is invoking the current backend image and inspect the next run result.'
        : health.scheduler_state === 'COLLECTION_OBSERVED_CURRENT'
          ? 'No immediate operator action is required. Continue monitoring source freshness and coverage.'
          : 'Confirm scheduler configuration and complete the first authorized collection.'

  return <div className="surface monitor-surface">
    <header className="page-title monitor-title"><span className="eyebrow">Administrator operations</span><h1>Source Health</h1><p>Collection, provider, scheduler, and resumable coverage status. Seller-facing decisions remain in Intelligence.</p></header>
    <div className="monitor-summary-grid" aria-label="Source Health summary">
      <article><span>Overall collection</span><strong>{schedulerLabel(health.scheduler_state)}</strong><small>{sourceState(health.worker_runtime_state)}</small></article>
      <article><span>Last successful execution</span><strong className="monitor-summary-date">{utcDateTime(lastSuccessfulRun?.completed_at)}</strong><small>{lastSuccessfulRun ? 'Recorded without a blocking collection failure' : 'No successful scheduled execution is recorded'}</small></article>
      <article><span>Next expected execution</span><strong className="monitor-summary-date">{health.scheduler_state === 'SCHEDULE_NOT_CONFIRMED' ? 'Not scheduled' : 'Managed by scheduler'}</strong><small>An exact next-run time is not reported by this runtime.</small></article>
      <article><span>Last-good content</span><strong>{persisted?.available ? 'Available' : 'Unavailable'}</strong><small>{persisted?.available ? `${persisted.returned}${persisted.more_available ? '+' : ''} current assessments in this bounded operational view` : 'No current persisted assessment is reported'}</small></article>
    </div>

    <Panel title="Operator decision" action={<StatusBadge value={health.scheduler_state} kind="source" label={schedulerLabel(health.scheduler_state)} />}>
      <p className="monitor-operator-action"><strong>What to do next:</strong> {operatorAction}</p>
      <dl className="monitor-decision-counts" aria-label="Latest governed collection counts">
        <div><dt>Accepted for seller review</dt><dd>{accepted}</dd></div>
        <div><dt>Requires review</dt><dd>{reviewRequired}</dd></div>
        <div><dt>Rejected in latest run</dt><dd>{latestRun?.records_rejected ?? 0}</dd></div>
        <div><dt>Awaiting continuation</dt><dd>{pendingCoverage.length}</dd></div>
      </dl>
      <p className="muted">These are bounded operational records, not a claim about the total addressable market.</p>
      <Button onClick={onIntelligence}>Open seller Intelligence</Button>
    </Panel>

    <div className="monitor-status-grid">
      <Panel title="Source freshness and coverage" action={<span className="panel-kicker">{health.sources.length} governed sources</span>}>
        <div className="card-list monitor-source-list">
          {health.sources.length ? health.sources.map(source => {
            const sourceCoverage = coverage.filter(item => item.query_key.startsWith(`${source.source_id}:`) || item.query_key === source.source_id)
            const pending = sourceCoverage.filter(item => item.pending_continuation).length
            return <article className="line" key={source.source_id}>
              <span><strong>{source.source_name ?? 'Configured source'}</strong><small>Last successful check: {utcDateTime(source.last_success_at)}</small><small>{source.failure_summary ?? (pending ? `${pending} governed queries will continue from saved checkpoints.` : 'No current source failure is reported.')}</small></span>
              <StatusBadge value={source.state ?? 'UNAVAILABLE'} kind="source" label={sourceState(source.state)} />
            </article>
          }) : <Empty>No governed sources are configured.</Empty>}
        </div>
      </Panel>
      <Panel title="Resumable procurement coverage" action={<span className="panel-kicker">{completeCoverage.length} complete · {pendingCoverage.length} continuing</span>}>
        {coverage.length ? <><p>Each governed query retains its own window and continuation state. Incomplete windows continue on later worker runs.</p><div className="monitor-coverage-list">{coverage.map(item => <article key={item.query_key}><span><strong>{item.query_value || 'Governed query'}</strong><small>{item.window_start} to {item.window_end}</small></span><StatusBadge value={item.coverage_state} kind="source" label={item.pending_continuation ? 'Awaiting continuation' : presentationLabel(item.coverage_state, 'provider')} /></article>)}</div></> : <Empty>No resumable procurement coverage checkpoint is available.</Empty>}
      </Panel>
    </div>

    <Disclosure title={`Run history and exact diagnostics (${health.last_runs.length})`} className="monitor-admin-disclosure">
      <p>Exact run identifiers, stage counts, failures, and provider receipts are administrator evidence. A run record does not by itself prove successful collection.</p>
      {health.last_runs.length ? health.last_runs.map((run, index) => <details key={run.id ?? `${run.source_id}:${run.completed_at}:${index}`} className="monitor-run-funnel"><summary>{run.source_id} · {run.completed_at ? utcDateTime(run.completed_at) : 'Run unfinished'} · {blockingFailures(run.failures).length ? 'Action required' : 'No blocking failure recorded'}</summary><p>Run {run.id ?? 'identifier unavailable'}.</p>{run.failures?.length ? <ul>{run.failures.map(item => <li key={item}>{item}</li>)}</ul> : <p>No run failure was recorded.</p>}{run.funnel ? <CanonicalRecord value={run.funnel} /> : <p>No stage-level diagnostics were recorded.</p>}</details>) : <Empty>No run history is available.</Empty>}
    </Disclosure>

    <Disclosure title={`Retained operational evidence (${currentEvents.length})`} className="monitor-admin-disclosure">
      <p>These retained records may be unresolved, rejected, or informational. Their presence does not make them seller recommendations.</p>
      {currentEvents.length ? currentEvents.map(event => <details key={event.id} className="monitor-collected-record"><summary>{event.source_id} · {presentationLabel(event.resolution_state, 'assessment')} · {utcDateTime(event.collected_at)}</summary><p>Operational record: {event.id}</p><p>Seller relevance: {presentationLabel(event.seller_relevance_state ?? 'UNASSESSED', 'assessment')}</p><EvidencePassages eventId={event.id} /></details>) : <Empty>No retained operational evidence is available.</Empty>}
    </Disclosure>

    {settings?.capabilities.view_integration_diagnostics && <Disclosure title="Provider and integration details" className="monitor-admin-disclosure"><p>Configuration is deployment managed. Secret values and credentials are never returned.</p><div className="integration-list">{Object.entries(settings.integrations).map(([id, integration]) => <article className="integration-row" key={id}><div><strong>{integrationNames[id] ?? 'Configured integration'}</strong><span>{integration.detail}</span></div><StatusBadge value={integration.state} kind="integration" /></article>)}</div><p><strong>Research synthesis:</strong> {presentationLabel(health.brief_synthesis_status, 'provider')}</p><p><strong>Durable run state:</strong> {health.durable_run_state ? 'Available' : 'Unavailable'}</p></Disclosure>}
  </div>
}
