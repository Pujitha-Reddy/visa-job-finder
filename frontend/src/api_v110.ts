import type { Job, JobSort } from "./types";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_BASE ||
  "http://127.0.0.1:8000";

type FetchJobParams = {
  hours: number;
  sourceType?: string;
  agency?: string;
  employmentDetail?: string;
  visaDetail?: string;
  experienceBand?: string;
  workArrangement?: string;
  applicationStatus?: string;
  query?: string;
  sort?: JobSort;
};

function extractItems(payload: any): any[] {
  if (Array.isArray(payload)) return payload;

  if (payload && Array.isArray(payload.items)) {
    return payload.items;
  }

  if (payload && Array.isArray(payload.jobs)) {
    return payload.jobs;
  }

  if (payload && Array.isArray(payload.results)) {
    return payload.results;
  }

  return [];
}

function mapCanonicalJob(raw: any): Job {
  const freshnessScore = Number(raw.freshness_score ?? 0);

  const freshnessConfidence =
    freshnessScore >= 80
      ? "HIGH"
      : freshnessScore >= 60
        ? "MEDIUM"
        : "UNKNOWN";

  return {
    id: raw.id,

    company_name_raw:
      raw.employer ||
      "Employer unavailable",

    employer:
      raw.employer ?? null,

    employer_domain:
      raw.employer_domain ?? null,

    title:
      raw.title ||
      "Untitled role",

    source: "CANONICAL",

    source_url:
      raw.source_url || "",

    apply_url:
      raw.apply_url || raw.source_url || null,

    source_type:
      "DIRECT_EMPLOYER",

    location_raw:
      raw.location || null,

    location:
      raw.location || null,

    posted_at:
      raw.posted_at ?? null,

    source_published_at:
      raw.posted_at ?? null,

    effective_posted_at:
      raw.posted_at ?? null,

    freshness_confidence:
      freshnessConfidence,

    freshness_source:
      "CANONICAL",

    min_experience_years:
      raw.min_experience_years ?? null,

    max_experience_years:
      raw.max_experience_years ?? null,

    experience_text:
      null,

    experience_match:
      null,

    experience_band:
      raw.seniority_band ?? null,

    seniority_band:
      raw.seniority_band ?? null,

    work_arrangement:
      raw.work_arrangement || "UNKNOWN",

    employment_type:
      "UNKNOWN",

    employment_detail_type:
      null,

    visa_language_status:
      raw.visa_language_status || "NO_EXPLICIT_LANGUAGE",

    visa_detail_status:
      null,

    visa_evidence_text:
      raw.visa_language_evidence ?? null,

    visa_language_evidence:
      raw.visa_language_evidence ?? null,

    h1b_history_strength:
      raw.sponsor_history_strength || "UNKNOWN",

    sponsor_history_strength:
      raw.sponsor_history_strength || "UNKNOWN",

    sponsor_recent_filings:
      raw.sponsor_recent_filings ?? null,

    sponsor_recent_approvals:
      raw.sponsor_recent_approvals ?? null,

    sponsorship_score:
      Number(raw.sponsorship_score ?? 0),

    overall_score:
      Number(raw.overall_score ?? 0),

    source_confidence_score:
      raw.best_source_confidence ?? null,

    source_confidence_label:
      null,

    decision:
      "APPLY",

    decision_reason:
      raw.eligibility_reason ?? null,

    application_status:
      raw.application_status || "NEW",

    date_applied:
      raw.date_applied ?? null,

    is_active:
      true,

    last_verified_at:
      raw.last_seen_at ?? null,

    disappeared_at:
      null,

    software_role_family:
      raw.software_role_family ?? null,

    state_code:
      raw.state_code ?? null,

    city:
      raw.city ?? null,

    country_code:
      raw.country_code ?? null,

    sponsorship_eligibility:
      raw.sponsorship_eligibility ?? null,

    eligibility_reason:
      raw.eligibility_reason ?? null,
  };
}


function matchesFreshness(job: Job, hours: number) {
  const raw =
    job.source_published_at ||
    job.effective_posted_at ||
    job.posted_at;

  // Do not discard otherwise useful jobs solely because an
  // upstream employer did not expose a reliable publish date.
  if (!raw) return true;

  const date = new Date(raw);

  if (Number.isNaN(date.getTime())) {
    return true;
  }

  const ageHours =
    (Date.now() - date.getTime()) /
    (1000 * 60 * 60);

  return ageHours <= hours;
}


function matchesExperience(
  job: Job,
  band?: string,
) {
  if (!band) return true;

  const min = job.min_experience_years;

  if (band === "NOT_SPECIFIED") {
    return min == null;
  }

  if (band === "NEW_GRAD") {
    return min == null || min <= 1;
  }

  if (min == null) {
    return true;
  }

  const match = band.match(
    /^(\d+)-(\d+)$/
  );

  if (!match) return true;

  const low = Number(match[1]);
  const high = Number(match[2]);

  return min >= low && min <= high;
}


function sortJobs(
  jobs: Job[],
  sort: JobSort,
) {
  const copy = [...jobs];

  if (sort === "newest") {
    return copy.sort((a, b) => {
      const av = new Date(
        a.source_published_at ||
        a.effective_posted_at ||
        a.posted_at ||
        0,
      ).getTime();

      const bv = new Date(
        b.source_published_at ||
        b.effective_posted_at ||
        b.posted_at ||
        0,
      ).getTime();

      return bv - av;
    });
  }

  if (sort === "sponsor") {
    return copy.sort(
      (a, b) =>
        b.sponsorship_score -
        a.sponsorship_score,
    );
  }

  if (sort === "experience") {
    return copy.sort(
      (a, b) =>
        (a.min_experience_years ?? 999) -
        (b.min_experience_years ?? 999),
    );
  }

  if (sort === "company") {
    return copy.sort(
      (a, b) =>
        a.company_name_raw.localeCompare(
          b.company_name_raw,
        ),
    );
  }

  return copy.sort(
    (a, b) =>
      b.overall_score -
      a.overall_score,
  );
}


async function fetchCanonicalPages(
  params: FetchJobParams,
) {
  const all: any[] = [];

  const pageSize = 200;
  let offset = 0;
  let total = Infinity;

  while (offset < total) {
    const search = new URLSearchParams();

    search.set("limit", String(pageSize));
    search.set("offset", String(offset));
    search.set("diversify", "false");

    search.set(
      "application_status",
      params.applicationStatus || "NEW",
    );

    if (params.query?.trim()) {
      search.set(
        "q",
        params.query.trim(),
      );
    }

    if (params.workArrangement) {
      search.set(
        "work_arrangement",
        params.workArrangement,
      );
    }

    if (params.visaDetail) {
      search.set(
        "visa_status",
        params.visaDetail,
      );
    }

    // sourceType has been repurposed in the UI as
    // sponsor-history strength.
    if (params.sourceType) {
      search.set(
        "sponsor_strength",
        params.sourceType,
      );
    }

    const response = await fetch(
      `${API_BASE}/v110/jobs?${search.toString()}`,
    );

    if (!response.ok) {
      throw new Error(
        `Failed to load canonical jobs: ${response.status}`,
      );
    }

    const payload = await response.json();

    const items = extractItems(payload);

    all.push(...items);

    total =
      typeof payload?.count === "number"
        ? payload.count
        : all.length;

    if (items.length === 0) {
      break;
    }

    offset += items.length;

    // Defensive ceiling. Current production inventory is far
    // below this, but a bad API count should never create an
    // infinite browser request loop.
    if (offset >= 5000) {
      break;
    }
  }

  return all;
}


export async function fetchJobs(
  params: FetchJobParams,
): Promise<Job[]> {
  const raw = await fetchCanonicalPages(
    params,
  );

  let jobs = raw.map(
    mapCanonicalJob,
  );

  jobs = jobs.filter(
    (job) =>
      matchesFreshness(
        job,
        params.hours,
      ),
  );

  jobs = jobs.filter(
    (job) =>
      matchesExperience(
        job,
        params.experienceBand,
      ),
  );

  return sortJobs(
    jobs,
    params.sort || "best",
  );
}


export async function fetchStats(
  _hours: number,
  sponsorStrength = "",
) {
  const search = new URLSearchParams({
    limit: "1",
    offset: "0",
    application_status: "NEW",
  });

  if (sponsorStrength) {
    search.set(
      "sponsor_strength",
      sponsorStrength,
    );
  }

  const response = await fetch(
    `${API_BASE}/v110/jobs?${search.toString()}`,
  );

  if (!response.ok) {
    throw new Error(
      `Failed to load canonical stats: ${response.status}`,
    );
  }

  const payload = await response.json();

  return {
    total:
      typeof payload?.count === "number"
        ? payload.count
        : extractItems(payload).length,
  };
}


export async function updateJobStatus(
  jobId: number,
  status: string,
) {
  const response = await fetch(
    `${API_BASE}/v110/jobs/${jobId}/status`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        status,
      }),
    },
  );

  if (!response.ok) {
    throw new Error(
      `Failed to update canonical job status: ${response.status}`,
    );
  }

  return response.json();
}
