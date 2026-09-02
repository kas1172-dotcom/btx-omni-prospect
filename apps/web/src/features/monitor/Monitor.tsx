import type { MonitorHealth, MonitorPreviewSignal } from "../../types/api";
import { SignalBriefCard } from "../../components/SignalBriefCard";
import { Empty, Panel, State } from "../../components/UI";
import "./monitor.css";

const validation = (state: string) =>
  ({
    BROWSER_VERIFIED: "Browser verified",
    AUTOMATION_BLOCKED: "Automated validation blocked",
    REPLACED_WITH_EQUIVALENT_OFFICIAL_SOURCE: "Equivalent official source",
    NEEDS_RESEARCH: "Source validation needs research",
  })[state] ?? "Source validation unavailable";

const utcDate = (value: string) =>
  new Date(value).toLocaleDateString("en-US", { timeZone: "UTC" });

const schedulerLabel = (state: string) =>
  ({
    SCHEDULE_NOT_CONFIRMED: "Schedule not confirmed",
    SCHEDULE_CONFIGURED_AWAITING_RUN: "Awaiting first run",
    LATEST_SCHEDULED_RUN_FAILED: "Latest run failed",
    COLLECTION_OBSERVED_STALE: "Collection stale",
    COLLECTION_OBSERVED_CURRENT: "Collection current",
  })[state] ?? "Schedule unavailable";

function PreviewCard({
  signal,
  onAccount,
  onIntelligence,
}: {
  signal: MonitorPreviewSignal;
  onAccount: (id: string) => void;
  onIntelligence: () => void;
}) {
  return (
    <article className="card monitor-preview-card">
      <div className="monitor-preview-head">
        <div>
          <span className="eyebrow">
            {signal.event_type.replaceAll("_", " ")}
          </span>
          <h3>{signal.company}</h3>
          <small>
            {utcDate(signal.event_date)} UTC · {signal.industry}
          </small>
        </div>
        <div className="monitor-states">
          <State value="CURATED PUBLIC · NOT LIVE INGESTION" />
          <State value={signal.evidence_state} />
        </div>
      </div>
      <p>
        <strong>What happened:</strong> {signal.title}
      </p>
      <div className="monitor-preview-meta">
        <span>
          <strong>Validation</strong>
          {validation(signal.source_validation_state)}
        </span>
        <span>
          <strong>Monitor state</strong>Not live ingestion
        </span>
      </div>
      <div className="card-actions">
        <a href={signal.source_url} target="_blank" rel="noreferrer">
          Open source ↗
        </a>
        <button onClick={() => onAccount(signal.account_id)}>
          Open Customer 360
        </button>
        <button onClick={onIntelligence}>Open Intelligence</button>
      </div>
    </article>
  );
}

export function Monitor({
  health,
  onAccount,
  onIntelligence,
}: {
  health?: MonitorHealth;
  onAccount: (id: string) => void;
  onIntelligence: () => void;
}) {
  const collected =
    health?.events?.filter((event) => event.data_mode === "LIVE_PUBLIC") ?? [];
  const live =
    health?.signal_briefs?.filter(
      (brief) =>
        brief.resolution_state === "RESOLVED" &&
        brief.seller_promotion_state === "RESOLVED_ELIGIBLE" &&
        brief.freshness === "CURRENT",
    ) ?? [];
  return (
    <div className="surface monitor-surface">
      <div className="page-title monitor-title">
        <span className="eyebrow">Intelligence inbox</span>
        <h1>Monitor</h1>
        <p>
          Public-source monitoring is governed separately from seller workflow
          and is never started from this UI.
        </p>
      </div>
      {!health ? (
        <Empty>Monitor status is unavailable.</Empty>
      ) : (
        <>
          <p className="truth-note">
            {health.seller_message}{" "}
            {health.durable_run_state
              ? ""
              : "Run history is not durable in this POC."}
          </p>
          <div className="monitor-summary-grid" aria-label="Monitor summary">
            <article>
              <span>Collection state</span>
              <strong>{schedulerLabel(health.scheduler_state)}</strong>
              <small>{health.last_runs.length} recorded runs</small>
            </article>
            <article>
              <span>Live public events</span>
              <strong>{collected.length}</strong>
              <small>{live.length} current seller briefs</small>
            </article>
            <article>
              <span>Curated preview</span>
              <strong>{health.curated_preview.length}</strong>
              <small>Stored public POC scenarios</small>
            </article>
          </div>
          <div className="monitor-status-grid">
            <Panel
              title="Collection status"
              action={
                <State value={schedulerLabel(health.scheduler_state)} />
              }
            >
              <p>
                {health.last_runs.length
                  ? `${health.last_runs.length} run records available.`
                  : "No collection runs have been recorded."}
              </p>
              <small>
                Only a successful recent collection may be labeled live public
                evidence. This UI cannot start, schedule, or alter collection.
              </small>
            </Panel>
            <Panel
              title="Source freshness"
              action={
                <span className="panel-kicker">
                  {health.sources.length} sources
                </span>
              }
            >
              <div className="card-list monitor-source-list">
                {health.sources.length ? (
                  health.sources.map((source) => (
                    <div className="line" key={source.source_id}>
                      <span>
                        <strong>
                          {source.source_name ?? source.source_id}
                        </strong>
                        <small>
                          Last successful check:{" "}
                          {source.last_success_at
                            ? `${utcDate(source.last_success_at)} UTC`
                            : "Unavailable"}
                        </small>
                        <small>
                          {source.failure_summary ??
                            (source.state === "NEVER_ATTEMPTED"
                              ? "No collection attempt recorded."
                              : "No current source failure.")}
                        </small>
                      </span>
                      <State
                        value={(source.state ?? "NEVER_ATTEMPTED").replaceAll(
                          "_",
                          " ",
                        )}
                      />
                    </div>
                  ))
                ) : (
                  <Empty>No sources are configured.</Empty>
                )}
              </div>
            </Panel>
          </div>
          <Panel
            title="Live public results"
            action={
              <span className="panel-kicker">
                {collected.length} collected · {live.length} current briefs
              </span>
            }
          >
            <p className="monitor-intro">
              Only resolved, evidence-backed events with a current publication
              date are eligible for seller Intelligence. Unresolved or stale
              output remains operational evidence, not a seller recommendation.
            </p>
            {live.length ? (
              <div className="card-list monitor-live-list">
                {live.map((brief) => <SignalBriefCard key={brief.id} brief={brief} onAccount={onAccount} />)}
              </div>
            ) : (
              <Empty>
                No resolved, evidence-backed current signal brief is
                seller-visible from the latest durable collection state.
              </Empty>
            )}
          </Panel>
          <Panel
            title="Curated POC signal preview"
            action={
              <span className="panel-kicker">
                {health.curated_preview.length} stored public events
              </span>
            }
          >
            <p className="monitor-intro">
              These are stored, sourced public scenarios used to demonstrate
              Monitor output. They are curated POC material, not a collection
              result. {health.scheduler_state === "COLLECTION_OBSERVED_CURRENT"
                ? "Scheduled collection evidence is reported separately above."
                : "No active scheduler is verified."}
            </p>
            <p className="muted">
              Production monitoring needs an approved source registry,
              collection credentials where required, durable run history, entity
              resolution, and alert policy.
            </p>
            {health.curated_preview.length ? (
              <div className="monitor-preview-grid">
                {health.curated_preview.map((signal) => (
                  <PreviewCard
                    key={signal.id}
                    signal={signal}
                    onAccount={onAccount}
                    onIntelligence={onIntelligence}
                  />
                ))}
              </div>
            ) : (
              <Empty>
                No curated public events are available for this POC preview.
              </Empty>
            )}
          </Panel>
        </>
      )}
    </div>
  );
}
