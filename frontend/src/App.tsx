import UnifiedFilterPanel from "./UnifiedFilterPanel";
import { useEffect, useMemo, useState } from "react";
import { fetchStats, updateJobStatus, fetchV78Jobs } from "./api";
import type { Filters, Job } from "./types";

const defaultFilters: Filters = {
  hours: 24,
  query: "",
  work: new Set(["REMOTE", "HYBRID", "ONSITE", "UNKNOWN"]),
  employment: new Set([
    "FULL_TIME",
    "CONTRACT_W2",
    "CONTRACT_C2C",
    "CONTRACT_UNKNOWN",
    "UNKNOWN",
  ]),
  visa: new Set([
    "SPONSORSHIP_AVAILABLE",
    "OPT_F1_MENTIONED",
    "NOT_MENTIONED",
    "UNKNOWN",
  ]),
  decision: new Set(["APPLY", "OK_TO_APPLY", "NEEDS_REVIEW"]),
  applicationStatus: "NEW",
};

function toggle(
  setter: React.Dispatch<React.SetStateAction<Filters>>,
  key: keyof Filters,
  value: string
) {
  setter((prev) => {
    const next = new Set(prev[key] as Set<string>);
    next.has(value) ? next.delete(value) : next.add(value);

    return {
      ...prev,
      [key]: next,
    };
  });
}

function badgeClass(kind: string) {
  if (
    ["APPLY", "REMOTE", "STRONG", "SPONSORSHIP_AVAILABLE"].includes(kind)
  ) {
    return "badge good";
  }

  if (
    [
      "OK_TO_APPLY",
      "HYBRID",
      "MEDIUM",
      "OPT_F1_MENTIONED",
      "F1_OPT_COMPATIBLE_SIGNAL",
      "WORK_AUTHORIZATION_MENTIONED",
    ].includes(kind)
  ) {
    return "badge warn";
  }

  if (
    ["SKIP", "NO_SPONSORSHIP", "RESTRICTED"].includes(kind)
  ) {
    return "badge bad";
  }

  return "badge neutral";
}

function App() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [filters, setFilters] = useState<Filters>(defaultFilters);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [sourceType, setSourceType] = useState("");
  const [agency, setAgency] = useState("");
  const [employmentDetail, setEmploymentDetail] = useState("");
  const [visaDetail, setVisaDetail] = useState("");
  const [experienceBand, setExperienceBand] = useState("");

  useEffect(() => {
    setLoading(true);

    Promise.all([
      fetchV78Jobs({
        hours: filters.hours,
        sourceType,
        agency,
        employmentDetail,
        visaDetail,
        experienceBand,
        applicationStatus: filters.applicationStatus,
      }),

      fetchStats(filters.hours),
    ])
      .then(([j, s]) => {
        setJobs(j);
        setStats(s);
        setError("");
      })
      .catch((err) => {
        setError(err.message);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [
    filters.hours,
    filters.applicationStatus,
    sourceType,
    agency,
    employmentDetail,
    visaDetail,
    experienceBand,
  ]);

  const filtered = useMemo(() => {
    const q = filters.query.trim().toLowerCase();

    return jobs.filter((job) => {
      const matchesQuery =
        !q ||
        `${job.title} ${job.company_name_raw} ${job.location_raw || ""}`
          .toLowerCase()
          .includes(q);

      return (
        matchesQuery &&
        filters.work.has(job.work_arrangement) &&
        filters.decision.has(job.decision)
      );
    });
  }, [jobs, filters]);

  async function refreshJobs() {
    const refreshedJobs = await fetchV78Jobs({
      hours: filters.hours,
      sourceType,
      agency,
      employmentDetail,
      visaDetail,
      experienceBand,
      applicationStatus: filters.applicationStatus,
    });

    setJobs(refreshedJobs);
  }

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">
            PERSONAL JOB SEARCH AUTOMATION
          </p>

          <h1>Visa Job Finder</h1>

          <p className="subtitle">
            Software engineering roles ranked by fit, work arrangement,
            experience, and sponsorship evidence.
          </p>
        </div>

        <div className="heroStat">
          <span>{filtered.length}</span>
          <small>matching jobs</small>
        </div>
      </header>

      <div className="stats">
        <div>
          <strong>{stats?.total ?? 0}</strong>
          <span>Total</span>
        </div>

        <div>
          <strong>{stats?.remote ?? 0}</strong>
          <span>Remote</span>
        </div>

        <div>
          <strong>{stats?.hybrid ?? 0}</strong>
          <span>Hybrid</span>
        </div>

        <div>
          <strong>{stats?.review_count ?? 0}</strong>
          <span>Needs Review</span>
        </div>
      </div>

      <main className="layout">
        <aside className="filters">
          <h2>Filters</h2>

          <UnifiedFilterPanel
            hours={filters.hours}
            setHours={(hours) =>
              setFilters((prev) => ({
                ...prev,
                hours: hours as 24 | 72,
              }))
            }

            query={filters.query}
            setQuery={(query) =>
              setFilters((prev) => ({
                ...prev,
                query,
              }))
            }

            applicationStatus={filters.applicationStatus}
            setApplicationStatus={(applicationStatus) =>
              setFilters((prev) => ({
                ...prev,
                applicationStatus,
              }))
            }

            sourceType={sourceType}
            setSourceType={setSourceType}

            agency={agency}
            setAgency={setAgency}

            employmentDetail={employmentDetail}
            setEmploymentDetail={setEmploymentDetail}

            visaDetail={visaDetail}
            setVisaDetail={setVisaDetail}

            experienceBand={experienceBand}
            setExperienceBand={setExperienceBand}
          />

          <FilterGroup title="Location">
            {["REMOTE", "HYBRID", "ONSITE", "UNKNOWN"].map((x) => (
              <Check
                key={x}
                label={x}
                checked={filters.work.has(x)}
                onChange={() =>
                  toggle(setFilters, "work", x)
                }
              />
            ))}
          </FilterGroup>

          <FilterGroup title="Decision">
            {[
              "APPLY",
              "OK_TO_APPLY",
              "NEEDS_REVIEW",
              "SKIP",
            ].map((x) => (
              <Check
                key={x}
                label={x.replaceAll("_", " ")}
                checked={filters.decision.has(x)}
                onChange={() =>
                  toggle(setFilters, "decision", x)
                }
              />
            ))}
          </FilterGroup>
        </aside>

        <section className="results">
          <div className="resultsHeader">
            <div>
              <h2>Jobs</h2>

              <p>
                {filters.hours === 24
                  ? "Last 24 hours"
                  : "Last 3 days"}
              </p>
            </div>
          </div>

          {loading && (
            <div className="state">
              Loading jobs…
            </div>
          )}

          {error && (
            <div className="state error">
              {error}
            </div>
          )}

          {!loading &&
            !error &&
            filtered.length === 0 && (
              <div className="state">
                No jobs match the current filters yet.
              </div>
            )}

          <div className="cards">
            {filtered.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                onStatus={async (status) => {
                  await updateJobStatus(
                    job.id,
                    status
                  );

                  await refreshJobs();
                }}
              />
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

function FilterGroup({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="group">
      <h3>{title}</h3>
      {children}
    </div>
  );
}

function Check({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <label className="check">
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
      />

      <span>{label}</span>
    </label>
  );
}

function JobCard({
  job,
  onStatus,
}: {
  job: Job;
  onStatus: (status: string) => Promise<void>;
}) {
  const employmentLabel =
    (job as any).employment_detail_type ||
    job.employment_type ||
    "UNKNOWN";

  const visaLabel =
    (job as any).visa_detail_status ||
    job.visa_language_status ||
    "UNKNOWN";

  const agencyName =
    (job as any).agency_name || "";

  return (
    <article className="jobCard">
      <div className="jobTop">
        <div>
          <p className="company">
            {job.company_name_raw}
          </p>

          {agencyName &&
            agencyName !== job.company_name_raw && (
              <p className="agency">
                Posted by {agencyName}
              </p>
            )}

          <h3>{job.title}</h3>

          <p className="meta">
            {job.location_raw ||
              "Location not listed"}
            {" · "}
            {employmentLabel.replaceAll(
              "_",
              " "
            )}
          </p>
        </div>

        <div className="score">
          <strong>
            {Math.round(
              job.overall_score ||
                job.sponsorship_score ||
                0
            )}
          </strong>

          <span>/100</span>
        </div>
      </div>

      <div className="badges">
        <span
          className={badgeClass(
            job.work_arrangement
          )}
        >
          {job.work_arrangement}
        </span>

        <span
          className={badgeClass(
            job.h1b_history_strength
          )}
        >
          H-1B {job.h1b_history_strength}
        </span>

        <span
          className={badgeClass(visaLabel)}
        >
          {visaLabel.replaceAll("_", " ")}
        </span>

        <span
          className={badgeClass(job.decision)}
        >
          {job.decision.replaceAll(
            "_",
            " "
          )}
        </span>
      </div>

      <div className="details">
        <div>
          <span>Experience</span>

          <strong>
            {job.experience_text ||
              "Needs review"}
          </strong>
        </div>

        <div>
          <span>Sponsor score</span>

          <strong>
            {Math.round(
              job.sponsorship_score || 0
            )}
            /100
          </strong>
        </div>
      </div>

      <p className="reason">
        {job.decision_reason ||
          "No additional decision notes."}
      </p>

      <div className="actions">
        <a
          href={
            job.apply_url ||
            job.source_url
          }
          target="_blank"
          rel="noreferrer"
          className="primary"
        >
          View / Apply
        </a>

        <button
          onClick={() =>
            onStatus("SAVED")
          }
        >
          Save
        </button>

        <button
          onClick={() =>
            onStatus("APPLIED")
          }
        >
          Mark Applied
        </button>

        <button
          className="ghost"
          onClick={() =>
            onStatus("SKIPPED")
          }
        >
          Skip
        </button>
      </div>
    </article>
  );
}

export default App;