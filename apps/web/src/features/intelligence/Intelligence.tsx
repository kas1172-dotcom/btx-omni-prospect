import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  Account,
  CommandCenter,
  MonitorHealth,
  MonitorSignalBrief,
  OmniContext,
  Signal,
  WorkspaceSettings,
} from "../../types/api";
import {
  Button,
  Disclosure,
  Empty,
  EvidenceSource,
  FilterChip,
  Panel,
  SearchInput,
  SelectInput,
  State,
} from "../../components/UI";
import { curatedSignalBrief } from "../../components/signalBriefModel";
import { FederalProcurementView } from "./FederalProcurement";
import { MarketIntelligence } from "./MarketIntelligence";
import "./intelligence.css";

type Filters = {
  customer: string;
  market: string;
  source: string;
  timing: string;
};
type Sort = "PRIORITY" | "MOST_RECENT" | "UPCOMING_EVENT" | "CUSTOMER";
const empty: Filters = { customer: "", market: "", source: "", timing: "" };
const markets = [
  "Commercial Aerospace",
  "Defense",
  "Space",
  "Semiconductor",
  "Medical",
  "Robotics",
  "Energy",
];
const label = (value: string) =>
  value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^./, (char) => char.toUpperCase());
const date = (value?: string) =>
  value
    ? new Date(value).toLocaleDateString("en-US", { timeZone: "UTC" })
    : "Unavailable";
const when = (brief: MonitorSignalBrief) =>
  brief.relevant_event_timestamp ??
  brief.publication_timestamp ??
  brief.collection_timestamp;
const mode = (value: string) =>
  ({
    LIVE_PUBLIC: "CONNECTED public",
    CURATED_PUBLIC: "SAMPLE public",
    SAMPLE: "SAMPLE BTX context",
  })[value] ?? label(value);
const unique = (values: string[]) =>
  [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b));

function matches(
  brief: MonitorSignalBrief,
  account: Account | undefined,
  query: string,
  filters: Filters,
) {
  const text = [
    brief.headline,
    brief.seller_summary,
    brief.what_happened,
    brief.why_it_may_matter,
    account?.name,
    account?.legal_name,
    ...brief.markets,
    brief.source_system,
    brief.canonical_program_id,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return (
    (!query || text.includes(query.toLowerCase())) &&
    (!filters.customer ||
      brief.canonical_account_ids.includes(filters.customer)) &&
    (!filters.market || brief.markets.includes(filters.market)) &&
    (!filters.source ||
      brief.source_system === filters.source ||
      label(brief.source_system) === filters.source) &&
    (!filters.timing || brief.event_timing === filters.timing)
  );
}

function Card({
  brief,
  rank,
  name,
  onAccount,
  onSelect,
  selected,
  onCreateAction,
}: {
  brief: MonitorSignalBrief;
  rank?: number;
  name: (id: string) => string;
  onAccount: (id: string) => void;
  onSelect: (brief: MonitorSignalBrief) => void;
  selected: boolean;
  onCreateAction: (brief: MonitorSignalBrief) => void;
}) {
  const accountId = brief.canonical_account_ids[0];
  return (
    <article
      className={`intelligence-card ${selected ? "selected" : ""}`}
      data-signal-id={brief.id}
    >
      <header>
        <div className="intelligence-card-kicker">
          {rank && <b>#{rank}</b>}
          <span>
            {brief.event_timing === "UPCOMING"
              ? "Forward radar"
              : label(brief.source_system)}
          </span>
          <span>{date(when(brief))}</span>
        </div>
        <div className="intelligence-card-states">
          <State value={mode(brief.data_mode)} />
          <State value={label(brief.freshness)} />
        </div>
      </header>
      <div className="intelligence-card-main">
        <button
          className="intelligence-customer-link"
          disabled={!accountId}
          onClick={() => accountId && onAccount(accountId)}
        >
          {accountId ? name(accountId) : "Customer association unavailable"}
        </button>
        <h3>{brief.headline}</h3>
        <p>{brief.seller_summary}</p>
      </div>
      <section className="intelligence-bottom-line">
        <span>Why it matters</span>
        <strong>{brief.why_it_may_matter}</strong>
        {brief.recommended_action && (
          <p>
            <b>Next:</b> {brief.recommended_action}
          </p>
        )}
      </section>
      <Disclosure title="Evidence, freshness, and context">
        <div className="intelligence-evidence">
          <p>
            <b>What happened:</b> {brief.what_happened}
          </p>
          <p>
            <b>Watch next:</b> {brief.what_to_watch}
          </p>
          <p>
            <b>Published:</b> {date(brief.publication_timestamp)} ·{" "}
            <b>Collected:</b> {date(brief.collection_timestamp)}
            {brief.relevant_event_timestamp && (
              <>
                {" "}
                · <b>Relevant event:</b> {date(brief.relevant_event_timestamp)}
              </>
            )}
          </p>
          <EvidenceSource
            title={brief.headline}
            source={brief.source_system}
            date={brief.publication_timestamp}
            evidenceState={brief.resolution_state}
            validationState={brief.seller_promotion_state}
            url={brief.source_url}
            detail={`Evidence references: ${brief.evidence_ids.length ? brief.evidence_ids.join(", ") : "Unavailable"}`}
          />
        </div>
      </Disclosure>
      <div className="intelligence-card-actions">
        <Button
          variant={selected ? "primary" : "secondary"}
          aria-pressed={selected}
          onClick={() => onSelect(brief)}
        >
          {selected ? "Clear Omni event" : "Use in Omni"}
        </Button>
        {brief.recommended_action && accountId && (
          <Button variant="ghost" onClick={() => onCreateAction(brief)}>
            Create Action
          </Button>
        )}
      </div>
    </article>
  );
}

export function Intelligence({
  signals,
  accounts,
  commandCenter,
  monitor,
  settings,
  onAccount,
  onEventSelect,
  onCreateAction,
  onOmniContext,
}: {
  signals: Signal[];
  accounts: Account[];
  commandCenter?: CommandCenter;
  monitor?: MonitorHealth;
  settings?: WorkspaceSettings;
  onAccount: (id: string) => void;
  onEventSelect: (id?: string) => void;
  onCreateAction: (brief: MonitorSignalBrief) => void;
  onOmniContext: (
    context: Pick<OmniContext, "active_filters" | "visible_record_ids">,
  ) => void;
}) {
  const [workspace, setWorkspace] = useState<"monitor" | "federal" | "markets">(() => window.location.hash.startsWith('#/intelligence/markets') ? 'markets' : window.location.hash.startsWith('#/intelligence/federal') ? 'federal' : 'monitor');
  useEffect(() => {
    const changed = () => setWorkspace(window.location.hash.startsWith('#/intelligence/markets') ? 'markets' : window.location.hash.startsWith('#/intelligence/federal') ? 'federal' : 'monitor');
    window.addEventListener('hashchange', changed);
    return () => window.removeEventListener('hashchange', changed);
  }, []);
  const selectWorkspace = (next: "monitor" | "federal" | "markets") => {
    setWorkspace(next);
    window.location.hash = `/intelligence${next === 'monitor' ? '' : `/${next}`}`;
  };
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<Filters>(empty);
  const [sort, setSort] = useState<Sort>("PRIORITY");
  const [selected, setSelected] = useState<string>();
  const byId = useMemo(
    () => new Map(accounts.map((account) => [account.id, account])),
    [accounts],
  );
  const name = useCallback(
    (id: string) =>
      byId.get(id)?.name ?? byId.get(id)?.legal_name ?? "Customer unavailable",
    [byId],
  );
  const curated = useMemo(
    () =>
      signals.map((signal) =>
        curatedSignalBrief(signal, byId.get(signal.account_id ?? "")),
      ),
    [byId, signals],
  );
  const priority = useMemo(
    () =>
      commandCenter?.priority_briefing
        .filter((item) => item.kind === "PUBLIC_SIGNAL" && item.signal_brief)
        .map((item) => item.signal_brief!) ?? [],
    [commandCenter],
  );
  const current = useMemo(
    () => commandCenter?.current_signal_briefs ?? [],
    [commandCenter],
  );
  const base = useMemo(() => {
    const items = new Map<string, MonitorSignalBrief>();
    [...priority, ...current, ...curated].forEach((item) =>
      items.set(item.id, item),
    );
    return [...items.values()];
  }, [priority, current, curated]);
  const visible = useMemo(
    () =>
      base.filter((item) =>
        matches(
          item,
          byId.get(item.canonical_account_ids[0] ?? ""),
          query,
          filters,
        ),
      ),
    [base, byId, filters, query],
  );
  const ordered = useMemo(
    () =>
      sort === "PRIORITY"
        ? visible
        : [...visible].sort((a, b) =>
            sort === "MOST_RECENT"
              ? when(b).localeCompare(when(a))
              : sort === "UPCOMING_EVENT"
                ? (a.relevant_event_timestamp ?? "9999").localeCompare(
                    b.relevant_event_timestamp ?? "9999",
                  )
                : name(a.canonical_account_ids[0] ?? "").localeCompare(
                    name(b.canonical_account_ids[0] ?? ""),
                  ),
          ),
    [name, sort, visible],
  );
  const ranked = useMemo(
    () =>
      priority
        .filter((item) =>
          matches(
            item,
            byId.get(item.canonical_account_ids[0] ?? ""),
            query,
            filters,
          ),
        )
        .slice(0, 5),
    [byId, filters, priority, query],
  );
  const radar = useMemo(
    () =>
      (commandCenter?.upcoming_radar ?? []).filter(
        (item) =>
          item.relevant_event_timestamp &&
          new Date(item.relevant_event_timestamp).getTime() > Date.now() &&
          matches(
            item,
            byId.get(item.canonical_account_ids[0] ?? ""),
            query,
            filters,
          ),
      ),
    [byId, commandCenter?.upcoming_radar, filters, query],
  );
  const active = useMemo(
    () =>
      Object.entries({ search: query, ...filters }).filter(
        ([, value]) => value,
      ),
    [filters, query],
  );
  const sources = unique(base.map((item) => item.source_system));
  const tracked = commandCenter?.watched_accounts ?? [];
  useEffect(() => () => onEventSelect(undefined), [onEventSelect]);
  useEffect(() => {
    if (workspace === 'markets') return;
    onOmniContext({
      active_filters: Object.fromEntries(active),
      visible_record_ids: ordered.map((item) => item.id).slice(0, 50),
    });
  }, [active, onOmniContext, ordered, workspace]);
  useEffect(() => () => onOmniContext({}), [onOmniContext]);
  const select = (brief: MonitorSignalBrief) => {
    const next = selected === brief.id ? undefined : brief.id;
    setSelected(next);
    onEventSelect(next);
  };
  const tiles = [
    {
      title: "Public intelligence",
      detail: `${current.length} current eligible signals`,
      state: commandCenter?.daily_briefing.live_intelligence_available
        ? "CONNECTED"
        : "UNAVAILABLE",
    },
    {
      title: "Internal commercial context",
      detail: "BTX commercial context is SAMPLE",
      state: "SAMPLE",
    },
    {
      title: "CRM / contacts",
      detail:
        settings?.integrations.hubspot?.detail ?? "Provider status unavailable",
      state: settings?.integrations.hubspot?.state ?? "NOT_CONFIGURED",
    },
    {
      title: "Quotes / RFQs",
      detail:
        settings?.integrations.paperless?.detail ??
        "Provider status unavailable",
      state: settings?.integrations.paperless?.state ?? "NOT_CONFIGURED",
    },
  ];
  if (workspace === 'markets') return <>
    <nav className="intelligence-tabs" aria-label="Intelligence modes">
      <Button onClick={() => selectWorkspace('monitor')}>Intelligence Monitor</Button>
      <Button onClick={() => selectWorkspace('federal')}>Federal Procurement</Button>
      <Button aria-current="page">Market Intelligence</Button>
    </nav>
    <MarketIntelligence accounts={accounts} onAccount={onAccount} onOmniContext={onOmniContext} />
  </>;
  if (workspace === "federal")
    return (
      <>
        <div className="surface intelligence-surface">
          <nav className="intelligence-tabs" aria-label="Intelligence modes">
            <Button onClick={() => selectWorkspace("monitor")}>
              Intelligence Monitor
            </Button>
            <Button aria-current="page">Federal Procurement</Button>
            <Button onClick={() => selectWorkspace('markets')}>Market Intelligence</Button>
          </nav>
        </div>
        <FederalProcurementView />
      </>
    );
  return (
    <div className="surface intelligence-surface">
      <nav className="intelligence-tabs" aria-label="Intelligence modes">
        <Button aria-current="page">Intelligence Monitor</Button>
        <Button onClick={() => selectWorkspace("federal")}>
          Federal Procurement
        </Button>
        <Button onClick={() => selectWorkspace('markets')}>Market Intelligence</Button>
      </nav>
      <header className="page-title intelligence-title">
        <span className="eyebrow">External Intelligence</span>
        <h1>Intelligence</h1>
        <p>What changed: prioritized evidence, Customer context, and governed next steps.</p>
      </header>
      <section
        className="intelligence-context-tiles"
        aria-label="Source and context status"
      >
        {tiles.map((tile) => (
          <article key={tile.title}>
            <span>{tile.title}</span>
            <strong>{tile.detail}</strong>
            <State value={tile.state} />
          </article>
        ))}
      </section>
      <section
        className="intelligence-priority"
        aria-labelledby="priority-signals"
      >
        <div className="section-heading">
          <div>
            <span className="eyebrow">Backend ranked</span>
            <h2 id="priority-signals">Today's Priority Signals</h2>
          </div>
          <span>{ranked.length} shown</span>
        </div>
        {ranked.length ? (
          <ol>
            {ranked.map((brief, index) => (
              <li key={brief.id}>
                <b>{index + 1}</b>
                <div>
                  <button
                    onClick={() =>
                      brief.canonical_account_ids[0] &&
                      onAccount(brief.canonical_account_ids[0])
                    }
                  >
                    {brief.canonical_account_ids[0]
                      ? name(brief.canonical_account_ids[0])
                      : "Customer unavailable"}
                  </button>
                  <strong>{brief.headline}</strong>
                  <span>{brief.what_happened}</span>
                </div>
                <small>
                  {date(when(brief))} · {mode(brief.data_mode)}
                </small>
              </li>
            ))}
          </ol>
        ) : (
          <Empty>No backend-ranked public signals are available.</Empty>
        )}
      </section>
      <section
        className="intelligence-tracked"
        aria-labelledby="tracked-targets"
      >
        <div className="section-heading">
          <div>
            <span className="eyebrow">System recommended · read only</span>
            <h2 id="tracked-targets">Tracked Customers & Prospects</h2>
          </div>
        </div>
        {tracked.length ? (
          <div>
            {tracked.map((item) => (
              <button
                key={item.account_id}
                onClick={() => onAccount(item.account_id)}
              >
                <strong>{item.name}</strong>
                <span>{item.markets.join(" · ")}</span>
                <small>
                  {item.reasons.length
                    ? "New signal context"
                    : "No new activity"}
                </small>
              </button>
            ))}
          </div>
        ) : (
          <Empty>No governed tracked targets are available.</Empty>
        )}
      </section>
      <section
        className="intelligence-controls"
        aria-label="Intelligence search and filters"
      >
        <SearchInput
          aria-label="Search Intelligence"
          placeholder="Search headline, Customer, market, source, program…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <div className="intelligence-filter-grid">
          <SelectInput
            aria-label="Filter Intelligence by Customer"
            value={filters.customer}
            onChange={(event) =>
              setFilters((value) => ({
                ...value,
                customer: event.target.value,
              }))
            }
          >
            <option value="">All Customers & Prospects</option>
            {accounts
              .filter((account) =>
                base.some((item) =>
                  item.canonical_account_ids.includes(account.id),
                ),
              )
              .map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name ?? account.legal_name}
                </option>
              ))}
          </SelectInput>
          <SelectInput
            aria-label="Filter Intelligence by market"
            value={filters.market}
            onChange={(event) =>
              setFilters((value) => ({ ...value, market: event.target.value }))
            }
          >
            <option value="">All markets</option>
            {markets
              .filter((market) =>
                base.some((item) => item.markets.includes(market)),
              )
              .map((market) => (
                <option key={market}>{market}</option>
              ))}
          </SelectInput>
          <SelectInput
            aria-label="Filter Intelligence by source"
            value={filters.source}
            onChange={(event) =>
              setFilters((value) => ({ ...value, source: event.target.value }))
            }
          >
            <option value="">All sources</option>
            {sources.map((item) => (
              <option key={item}>{label(item)}</option>
            ))}
          </SelectInput>
          <SelectInput
            aria-label="Filter Intelligence by timing"
            value={filters.timing}
            onChange={(event) =>
              setFilters((value) => ({ ...value, timing: event.target.value }))
            }
          >
            <option value="">All timing</option>
            <option value="OBSERVED">Observed</option>
            <option value="UPCOMING">Upcoming</option>
          </SelectInput>
          <SelectInput
            aria-label="Sort Intelligence"
            value={sort}
            onChange={(event) => setSort(event.target.value as Sort)}
          >
            <option value="PRIORITY">Sort: Priority</option>
            <option value="MOST_RECENT">Sort: Most Recent</option>
            <option value="UPCOMING_EVENT">Sort: Upcoming Event Date</option>
            <option value="CUSTOMER">Sort: Customer</option>
          </SelectInput>
        </div>
        {active.length > 0 && (
          <div className="intelligence-active-filters">
            {active.map(([key, value]) => (
              <FilterChip
                key={key}
                selected
                onClear={() =>
                  key === "search"
                    ? setQuery("")
                    : setFilters((current) => ({
                        ...current,
                        [key as keyof Filters]: "",
                      }))
                }
              >{`${label(key)}: ${value}`}</FilterChip>
            ))}
            <Button
              variant="ghost"
              onClick={() => {
                setQuery("");
                setFilters(empty);
                setSort("PRIORITY");
              }}
            >
              Clear all
            </Button>
          </div>
        )}
      </section>
      <Panel
        title="Intelligence Feed"
        action={
          <span className="panel-kicker">
            {ordered.length} governed signals ·{" "}
            {sort === "PRIORITY" ? "backend priority" : label(sort)}
          </span>
        }
        className="intelligence-feed-panel"
      >
        {ordered.length ? (
          <div className="intelligence-signal-list">
            {ordered.map((brief, index) => (
              <Card
                key={brief.id}
                brief={brief}
                rank={sort === "PRIORITY" ? index + 1 : undefined}
                name={name}
                onAccount={onAccount}
                onSelect={select}
                selected={selected === brief.id}
                onCreateAction={onCreateAction}
              />
            ))}
          </div>
        ) : (
          <Empty>
            No governed Intelligence matches the current search and filters.
          </Empty>
        )}
      </Panel>
      <Panel
        title="Forward Radar"
        action={
          <span className="panel-kicker">
            Future source-supported event dates only
          </span>
        }
        className="intelligence-radar"
      >
        {radar.length ? (
          <div className="intelligence-signal-list">
            {radar.map((brief) => (
              <Card
                key={brief.id}
                brief={brief}
                name={name}
                onAccount={onAccount}
                onSelect={select}
                selected={selected === brief.id}
                onCreateAction={onCreateAction}
              />
            ))}
          </div>
        ) : (
          <Empty>
            No upcoming source-supported events match the current filters.
            Undated signals are excluded.
          </Empty>
        )}
      </Panel>
      <Disclosure
        title={`Source health · ${monitor?.sources.length ?? 0} configured source records`}
        className="intelligence-source-health"
      >
        <div>
          {monitor?.sources.map((source) => (
            <p key={source.source_id}>
              <b>{source.source_name ?? source.source_id}</b> ·{" "}
              {label(source.state ?? "UNAVAILABLE")} · last collection{" "}
              {date(source.last_success_at)}
            </p>
          )) ?? <p>Monitor health is unavailable.</p>}
        </div>
      </Disclosure>
    </div>
  );
}
