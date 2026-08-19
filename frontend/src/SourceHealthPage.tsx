import { useEffect, useMemo, useState } from "react";

import {
  fetchSourceHealth,
  fetchSourceHealthSummary,
  fetchSourceRuns,
  type SourceHealth,
  type SourceHealthStatus,
  type SourceHealthSummary,
  type SourceRun,
} from "./source_health_api";

interface Props {
  onBack: () => void;
}

type FilterValue = "ALL" | SourceHealthStatus;

const FILTERS: FilterValue[] = [
  "ALL",
  "HEALTHY",
  "DEGRADED",
  "FAILING",
  "ZERO_RESULTS",
  "STALE",
  "NEVER_RUN",
];

function formatStatus(value: string) {
  return value.replace(/_/g, " ");
}

function formatDate(value: string | null) {
  if (!value) return "Never";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return date.toLocaleString();
}

function formatAge(hours: number | null) {
  if (hours == null) return "Never";

  if (hours < 1) {
    const minutes = Math.max(1, Math.floor(hours * 60));
    return `${minutes}m ago`;
  }

  if (hours < 24) {
    return `${Math.floor(hours)}h ago`;
  }

  return `${Math.floor(hours / 24)}d ago`;
}

function formatDuration(ms: number | null) {
  if (ms == null) return "—";

  if (ms < 1000) {
    return `${ms} ms`;
  }

  return `${(ms / 1000).toFixed(1)} s`;
}

function yieldPercent(row: SourceHealth) {
  if (!row.last_raw_jobs) {
    return "0%";
  }

  return `${Math.round(
    (row.last_eligible_jobs / row.last_raw_jobs) * 100
  )}%`;
}

function statusClass(value: string) {
  switch (value) {
    case "HEALTHY":
      return "sourceHealthStatus healthy";

    case "DEGRADED":
    case "ZERO_RESULTS":
    case "STALE":
      return "sourceHealthStatus warning";

    case "FAILING":
      return "sourceHealthStatus failing";

    case "NEVER_RUN":
      return "sourceHealthStatus neutral";

    default:
      return "sourceHealthStatus neutral";
  }
}

export default function SourceHealthPage({ onBack }: Props) {
  const [summary, setSummary] =
    useState<SourceHealthSummary | null>(null);

  const [sources, setSources] = useState<SourceHealth[]>([]);
  const [statusFilter, setStatusFilter] =
    useState<FilterValue>("ALL");

  const [query, setQuery] = useState("");

  const [selected, setSelected] =
    useState<SourceHealth | null>(null);

  const [runs, setRuns] = useState<SourceRun[]>([]);

  const [loading, setLoading] = useState(true);
  const [runsLoading, setRunsLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);

    try {
      const [summaryData, sourceData] =
        await Promise.all([
          fetchSourceHealthSummary(),
          fetchSourceHealth(),
        ]);

      setSummary(summaryData);
      setSources(sourceData);
      setError("");
    } catch (err: any) {
      setError(
        err?.message || "Failed to load source health."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function openSource(source: SourceHealth) {
    setSelected(source);
    setRuns([]);
    setRunsLoading(true);

    try {
      const data = await fetchSourceRuns(
        source.source_key,
        20
      );

      setRuns(data);
    } catch (err: any) {
      setError(
        err?.message ||
          "Failed to load source run history."
      );
    } finally {
      setRunsLoading(false);
    }
  }

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();

    return sources.filter((source) => {
      if (
        statusFilter !== "ALL" &&
        source.health_status !== statusFilter
      ) {
        return false;
      }

      if (!q) return true;

      return (
        source.employer_name
          .toLowerCase()
          .includes(q) ||
        source.ats
          .toLowerCase()
          .includes(q) ||
        (source.source_type || "")
          .toLowerCase()
          .includes(q)
      );
    });
  }, [sources, statusFilter, query]);

  return (
    <div className="page">
      <header className="hero adminHero">
        <div>
          <p className="eyebrow">
            COLLECTION OPERATIONS
          </p>

          <h1>Source Health</h1>

          <p className="subtitle">
            Monitor verified employer feeds, collection
            failures, eligibility yield, and source freshness.
          </p>
        </div>

        <button
          className="adminBackButton"
          onClick={onBack}
        >
          ← Job Finder
        </button>
      </header>

      <section className="sourceHealthSummary">
        <div>
          <strong>{summary?.sources ?? 0}</strong>
          <span>Sources</span>
        </div>

        <div>
          <strong>{summary?.healthy ?? 0}</strong>
          <span>Healthy</span>
        </div>

        <div>
          <strong>{summary?.degraded ?? 0}</strong>
          <span>Degraded</span>
        </div>

        <div>
          <strong>{summary?.failing ?? 0}</strong>
          <span>Failing</span>
        </div>

        <div>
          <strong>
            {summary?.zero_results ?? 0}
          </strong>
          <span>Zero results</span>
        </div>

        <div>
          <strong>{summary?.stale ?? 0}</strong>
          <span>Stale</span>
        </div>

        <div>
          <strong>
            {summary?.never_run ?? 0}
          </strong>
          <span>Never run</span>
        </div>
      </section>

      <div className="sourceHealthToolbar">
        <input
          className="sourceHealthSearch"
          value={query}
          onChange={(event) =>
            setQuery(event.target.value)
          }
          placeholder="Search employer or ATS..."
        />

        <button
          className="sourceRefreshButton"
          onClick={load}
          disabled={loading}
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      <nav
        className="sourceHealthFilters"
        aria-label="Source health filters"
      >
        {FILTERS.map((filter) => (
          <button
            key={filter}
            className={
              statusFilter === filter
                ? "active"
                : ""
            }
            onClick={() =>
              setStatusFilter(filter)
            }
          >
            {formatStatus(filter)}
          </button>
        ))}
      </nav>

      {error && (
        <div className="sourceHealthError">
          {error}
        </div>
      )}

      <div className="sourceHealthMeta">
        <span>
          Showing {filtered.length} of{" "}
          {sources.length} sources
        </span>

        <span>
          Latest success:{" "}
          {formatDate(
            summary?.latest_success_at ?? null
          )}
        </span>
      </div>

      <div className="sourceHealthTableWrap">
        <table className="sourceHealthTable">
          <thead>
            <tr>
              <th>Employer</th>
              <th>ATS</th>
              <th>Status</th>
              <th>Raw</th>
              <th>Eligible</th>
              <th>Yield</th>
              <th>Failures</th>
              <th>Last success</th>
            </tr>
          </thead>

          <tbody>
            {filtered.map((source) => (
              <tr
                key={source.source_key}
                onClick={() =>
                  openSource(source)
                }
              >
                <td>
                  <strong>
                    {source.employer_name}
                  </strong>

                  <small>
                    {source.source_type ||
                      "UNKNOWN"}
                  </small>
                </td>

                <td>
                  <span className="atsBadge">
                    {source.ats}
                  </span>
                </td>

                <td>
                  <span
                    className={statusClass(
                      source.health_status
                    )}
                  >
                    {formatStatus(
                      source.health_status
                    )}
                  </span>

                  <small>
                    {source.health_reason}
                  </small>
                </td>

                <td>
                  {source.last_raw_jobs}
                </td>

                <td>
                  {source.last_eligible_jobs}
                </td>

                <td>
                  {yieldPercent(source)}
                </td>

                <td>
                  {source.consecutive_failures}
                </td>

                <td>
                  {formatAge(
                    source.success_age_hours
                  )}
                </td>
              </tr>
            ))}

            {!loading &&
              filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={8}
                    className="sourceHealthEmpty"
                  >
                    No sources match the current
                    filters.
                  </td>
                </tr>
              )}
          </tbody>
        </table>
      </div>

      {selected && (
        <div
          className="sourceHealthOverlay"
          onClick={() =>
            setSelected(null)
          }
        >
          <aside
            className="sourceHealthDrawer"
            onClick={(event) =>
              event.stopPropagation()
            }
          >
            <div className="sourceDrawerHeader">
              <div>
                <p className="eyebrow">
                  SOURCE DETAILS
                </p>

                <h2>
                  {selected.employer_name}
                </h2>

                <p>
                  {selected.ats} ·{" "}
                  {selected.source_type}
                </p>
              </div>

              <button
                className="drawerClose"
                onClick={() =>
                  setSelected(null)
                }
                aria-label="Close source details"
              >
                ×
              </button>
            </div>

            <div className="sourceDrawerStats">
              <div>
                <span>Status</span>
                <strong>
                  {formatStatus(
                    selected.health_status
                  )}
                </strong>
              </div>

              <div>
                <span>Raw jobs</span>
                <strong>
                  {selected.last_raw_jobs}
                </strong>
              </div>

              <div>
                <span>Eligible</span>
                <strong>
                  {selected.last_eligible_jobs}
                </strong>
              </div>

              <div>
                <span>Yield</span>
                <strong>
                  {yieldPercent(selected)}
                </strong>
              </div>

              <div>
                <span>Runs / 24h</span>
                <strong>
                  {selected.runs_24h}
                </strong>
              </div>

              <div>
                <span>Failures / 24h</span>
                <strong>
                  {selected.failures_24h}
                </strong>
              </div>
            </div>

            {selected.last_error && (
              <div className="sourceLastError">
                <strong>Latest error</strong>
                <p>{selected.last_error}</p>
              </div>
            )}

            <div className="sourceDrawerLink">
              <span>Careers source</span>

              {selected.careers_url ? (
                <a
                  href={selected.careers_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open source ↗
                </a>
              ) : (
                <span>Unavailable</span>
              )}
            </div>

            <h3>Recent runs</h3>

            {runsLoading && (
              <p>Loading run history…</p>
            )}

            {!runsLoading &&
              runs.length === 0 && (
                <p className="sourceRunEmpty">
                  No collection runs recorded yet.
                </p>
              )}

            <div className="sourceRunList">
              {runs.map((run) => (
                <article
                  key={run.id}
                  className="sourceRunCard"
                >
                  <div className="sourceRunHeader">
                    <span
                      className={
                        run.success
                          ? "sourceRunSuccess"
                          : "sourceRunFailure"
                      }
                    >
                      {run.success
                        ? "SUCCESS"
                        : "FAILED"}
                    </span>

                    <span>
                      {formatDate(
                        run.completed_at
                      )}
                    </span>
                  </div>

                  <div className="sourceRunMetrics">
                    <span>
                      Raw{" "}
                      <strong>
                        {run.raw_jobs}
                      </strong>
                    </span>

                    <span>
                      Eligible{" "}
                      <strong>
                        {run.eligible_jobs}
                      </strong>
                    </span>

                    <span>
                      Excluded{" "}
                      <strong>
                        {run.excluded_jobs}
                      </strong>
                    </span>

                    <span>
                      Added{" "}
                      <strong>
                        {run.added_jobs}
                      </strong>
                    </span>

                    <span>
                      Updated{" "}
                      <strong>
                        {run.updated_jobs}
                      </strong>
                    </span>

                    <span>
                      Duration{" "}
                      <strong>
                        {formatDuration(
                          run.duration_ms
                        )}
                      </strong>
                    </span>
                  </div>

                  {run.error_message && (
                    <p className="sourceRunError">
                      {run.error_message}
                    </p>
                  )}
                </article>
              ))}
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
