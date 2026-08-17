import { useEffect, useMemo, useState } from "react";

import UnifiedFilterPanel from "./UnifiedFilterPanel";
import { fetchJobs, fetchStats, updateJobStatus } from "./api_v80";
import type { Filters, Job, JobSort } from "./types";

const defaultFilters: Filters = {
  hours: 24,
  query: "",
  applicationStatus: "NEW",
};

function matchBand(score: number) {
  if (score >= 80) return "STRONG MATCH";
  if (score >= 70) return "GOOD MATCH";
  if (score >= 60) return "REVIEW";
  return "LOW PRIORITY";
}

function postedAge(job: Job) {
  const value =
    job.source_published_at ||
    job.effective_posted_at ||
    job.posted_at;

  if (!value) return "Posting date unavailable";

  const posted = new Date(value);
  if (Number.isNaN(posted.getTime())) return "Posting date unavailable";

  const hours = (Date.now() - posted.getTime()) / (1000 * 60 * 60);

  if (hours < 1) return "Posted less than 1 hour ago";
  if (hours < 24) return `Posted ${Math.floor(hours)} hours ago`;

  const days = Math.floor(hours / 24);
  return days === 1 ? "Posted 1 day ago" : `Posted ${days} days ago`;
}

function experienceLabel(job: Job) {
  if (job.min_experience_years == null) return "Experience not specified";

  if (
    job.max_experience_years != null &&
    job.max_experience_years !== job.min_experience_years
  ) {
    return `${job.min_experience_years}–${job.max_experience_years} years`;
  }

  return `${job.min_experience_years}+ years`;
}

function visaLabel(job: Job) {
  const value =
    job.visa_detail_status ||
    job.visa_language_status ||
    "UNKNOWN";
  return value.replace(/_/g, " ");
}

function whyThisMatches(job: Job) {
  const reasons: string[] = [];
  const age = postedAge(job);

  if (!age.includes("unavailable")) reasons.push(age);

  if (job.min_experience_years != null) {
    reasons.push(`${job.min_experience_years}+ years experience requirement`);
  } else {
    reasons.push("Experience requirement not specified");
  }

  if (job.h1b_history_strength === "STRONG") {
    reasons.push("Strong historical H-1B sponsorship evidence");
  } else if (job.h1b_history_strength === "MEDIUM") {
    reasons.push("Moderate historical H-1B sponsorship evidence");
  }

  if (job.source_type === "DIRECT_EMPLOYER") reasons.push("Direct employer source");
  if (job.work_arrangement === "REMOTE") reasons.push("Remote opportunity");

  if (
    (job.visa_detail_status || job.visa_language_status) === "NOT_MENTIONED"
  ) {
    reasons.push("Visa sponsorship is not explicitly stated — review the posting");
  }

  return reasons;
}

function badgeTone(value: string) {
  if (
    ["STRONG", "REMOTE", "SPONSORSHIP_AVAILABLE", "F1_OPT_COMPATIBLE_SIGNAL"].includes(value)
  ) return "badge good";

  if (
    ["MEDIUM", "HYBRID", "NOT_MENTIONED", "WORK_AUTHORIZATION_MENTIONED"].includes(value)
  ) return "badge warn";

  if (
    ["NO_SPONSORSHIP", "RESTRICTED", "SKIPPED", "REJECTED"].includes(value)
  ) return "badge bad";

  return "badge neutral";
}

function App() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [filters, setFilters] = useState<Filters>(defaultFilters);

  const [sourceType, setSourceType] = useState("DIRECT_EMPLOYER");
  const [agency, setAgency] = useState("");
  const [employmentDetail, setEmploymentDetail] = useState("");
  const [visaDetail, setVisaDetail] = useState("");
  const [experienceBand, setExperienceBand] = useState("");
  const [workArrangement, setWorkArrangement] = useState("");
  const [sort, setSort] = useState<JobSort>("best");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadJobs() {
    setLoading(true);

    try {
      const [j, s] = await Promise.all([
        fetchJobs({
          hours: filters.hours,
          sourceType,
          agency,
          employmentDetail,
          visaDetail,
          experienceBand,
          workArrangement,
          applicationStatus: filters.applicationStatus,
          query: filters.query,
          sort,
        }),
        fetchStats(
          filters.hours,
          filters.applicationStatus === "NEW" ? sourceType : "",
        ),
      ]);

      setJobs(j);
      setStats(s);
      setError("");
    } catch (err: any) {
      setError(err?.message || "Failed to load jobs.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(loadJobs, filters.query ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [
    filters.hours,
    filters.query,
    filters.applicationStatus,
    sourceType,
    agency,
    employmentDetail,
    visaDetail,
    experienceBand,
    workArrangement,
    sort,
  ]);

  const title = useMemo(() => {
    switch (filters.applicationStatus) {
      case "SAVED": return "Saved jobs";
      case "APPLIED": return "Applications";
      case "INTERVIEW": return "Interviews";
      case "REJECTED": return "Rejected";
      case "SKIPPED": return "Skipped";
      default: return filters.hours === 24 ? "Fresh today" : "Last 3 days";
    }
  }, [filters.applicationStatus, filters.hours]);

  function openDiscovery(hours: 24 | 72) {
    setFilters((prev) => ({
      ...prev,
      hours,
      applicationStatus: "NEW",
    }));
    setSourceType("DIRECT_EMPLOYER");
    setSort("best");
  }

  function openHistory(status: string) {
    setFilters((prev) => ({
      ...prev,
      applicationStatus: status,
    }));
    setSourceType("");
  }

  async function changeStatus(jobId: number, status: string) {
    await updateJobStatus(jobId, status);
    await loadJobs();
  }

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">PERSONAL JOB SEARCH AUTOMATION</p>
          <h1>Visa Job Finder</h1>
          <p className="subtitle">
            Fresh U.S. software-engineering jobs ranked by experience fit,
            sponsorship evidence, employer quality, and location.
          </p>
        </div>

        <div className="heroStat">
          <span>{jobs.length}</span>
          <small>{title.toLowerCase()}</small>
        </div>
      </header>

      <nav className="quickNav" aria-label="Job views">
        <button
          className={filters.applicationStatus === "NEW" && filters.hours === 24 ? "active" : ""}
          onClick={() => openDiscovery(24)}
        >
          Today
        </button>
        <button
          className={filters.applicationStatus === "NEW" && filters.hours === 72 ? "active" : ""}
          onClick={() => openDiscovery(72)}
        >
          Last 3 Days
        </button>
        <button
          className={filters.applicationStatus === "SAVED" ? "active" : ""}
          onClick={() => openHistory("SAVED")}
        >
          Saved <span>{stats?.saved ?? 0}</span>
        </button>
        <button
          className={filters.applicationStatus === "APPLIED" ? "active" : ""}
          onClick={() => openHistory("APPLIED")}
        >
          Applied <span>{stats?.applied ?? 0}</span>
        </button>
        <button
          className={filters.applicationStatus === "INTERVIEW" ? "active" : ""}
          onClick={() => openHistory("INTERVIEW")}
        >
          Interviews <span>{stats?.interviews ?? 0}</span>
        </button>
      </nav>

      <div className="stats">
        <div><strong>{stats?.total ?? 0}</strong><span>Fresh jobs</span></div>
        <div><strong>{stats?.strong_matches ?? 0}</strong><span>Strong matches</span></div>
        <div><strong>{stats?.remote ?? 0}</strong><span>Remote</span></div>
        <div><strong>{stats?.applied ?? 0}</strong><span>Applied</span></div>
        <div><strong>{stats?.interviews ?? 0}</strong><span>Interviews</span></div>
      </div>

      <main className="layout">
        <aside className="filters">
          <div className="filterHeading">
            <div>
              <p className="eyebrow">DISCOVERY</p>
              <h2>Filters</h2>
            </div>

            <button
              className="resetButton"
              onClick={() => {
                setFilters(defaultFilters);
                setSourceType("DIRECT_EMPLOYER");
                setAgency("");
                setEmploymentDetail("");
                setVisaDetail("");
                setExperienceBand("");
                setWorkArrangement("");
                setSort("best");
              }}
            >
              Reset
            </button>
          </div>

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
            sourceType={sourceType}
            setSourceType={setSourceType}
            applicationStatus={filters.applicationStatus}
            setApplicationStatus={(applicationStatus) =>
              setFilters((prev) => ({
                ...prev,
                applicationStatus,
              }))
            }
            experienceBand={experienceBand}
            setExperienceBand={setExperienceBand}
            sort={sort}
            setSort={setSort}
            workArrangement={workArrangement}
            setWorkArrangement={setWorkArrangement}
            agency={agency}
            setAgency={setAgency}
            employmentDetail={employmentDetail}
            setEmploymentDetail={setEmploymentDetail}
            visaDetail={visaDetail}
            setVisaDetail={setVisaDetail}
          />
        </aside>

        <section className="results">
          <div className="resultsHeader">
            <div>
              <p className="eyebrow">PRIORITIZED QUEUE</p>
              <h2>{title}</h2>
              <p>
                {filters.applicationStatus === "NEW"
                  ? `${filters.hours}-hour source-backed freshness window`
                  : "Application history is preserved even after a posting closes"}
              </p>
            </div>

            <div className="resultCount">{jobs.length} jobs</div>
          </div>

          {loading && <div className="state">Loading jobs…</div>}
          {error && <div className="state error">{error}</div>}

          {!loading && !error && jobs.length === 0 && (
            <div className="state emptyState">
              <strong>No jobs match this view.</strong>
              <span>Try Last 3 Days or broaden one filter.</span>
            </div>
          )}

          <div className="cards">
            {jobs.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                onStatus={(status) => changeStatus(job.id, status)}
              />
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

function JobCard({
  job,
  onStatus,
}: {
  job: Job;
  onStatus: (status: string) => Promise<void>;
}) {
  const reasons = whyThisMatches(job);

  return (
    <article className="jobCard">
      <div className="jobTop">
        <div>
          <div className="cardKicker">
            <span>
              {job.source_type === "DIRECT_EMPLOYER"
                ? "DIRECT EMPLOYER"
                : job.source_type || job.source}
            </span>

            {job.application_status !== "NEW" && (
              <span>{job.application_status}</span>
            )}
          </div>

          <p className="company">{job.company_name_raw}</p>
          <h3>{job.title}</h3>

          <p className="meta">
            {job.location_raw || "Location unavailable"} · {job.work_arrangement}
          </p>

          <p className="postedAge">{postedAge(job)}</p>
        </div>

        <div className="scoreBlock">
          <div className="score">
            <strong>{Math.round(job.overall_score)}</strong>
            <span>/100</span>
          </div>
          <span className="matchBand">{matchBand(job.overall_score)}</span>
        </div>
      </div>

      <div className="badges">
        <span className={badgeTone(job.work_arrangement)}>{job.work_arrangement}</span>
        <span className={badgeTone(job.h1b_history_strength)}>
          H-1B {job.h1b_history_strength}
        </span>
        <span
          className={badgeTone(job.visa_detail_status || job.visa_language_status)}
        >
          {visaLabel(job)}
        </span>
        {job.source_type && (
          <span className="badge neutral">
            {job.source_type.replace(/_/g, " ")}
          </span>
        )}
      </div>

      <div className="details">
        <div><span>Experience</span><strong>{experienceLabel(job)}</strong></div>
        <div><span>Sponsor score</span><strong>{Math.round(job.sponsorship_score)}/100</strong></div>
        <div>
          <span>Employment</span>
          <strong>
            {(job.employment_detail_type || job.employment_type).replace(/_/g, " ")}
          </strong>
        </div>
        <div><span>Freshness</span><strong>{job.freshness_confidence || "UNKNOWN"}</strong></div>
      </div>

      <details className="why">
        <summary>Why this matches</summary>
        <ul>
          {reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      </details>

      {job.decision_reason && <p className="reason">{job.decision_reason}</p>}

      <div className="actions">
        <a
          className="primary"
          href={job.apply_url || job.source_url}
          target="_blank"
          rel="noreferrer"
        >
          View / Apply
        </a>

        {job.application_status !== "SAVED" && (
          <button onClick={() => onStatus("SAVED")}>Save</button>
        )}

        {job.application_status !== "APPLIED" && (
          <button onClick={() => onStatus("APPLIED")}>Mark Applied</button>
        )}

        {job.application_status === "APPLIED" && (
          <button onClick={() => onStatus("INTERVIEW")}>Interview</button>
        )}

        {job.application_status !== "SKIPPED" && (
          <button className="ghost" onClick={() => onStatus("SKIPPED")}>
            Skip
          </button>
        )}
      </div>
    </article>
  );
}

export default App;
