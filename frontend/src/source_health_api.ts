const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export type SourceHealthStatus =
  | "HEALTHY"
  | "DEGRADED"
  | "FAILING"
  | "ZERO_RESULTS"
  | "STALE"
  | "NEVER_RUN"
  | "DISABLED"
  | "UNVERIFIED";

export interface SourceHealthSummary {
  sources: number;
  verified_sources: number;
  enabled_sources: number;

  healthy: number;
  degraded: number;
  failing: number;
  zero_results: number;
  stale: number;
  never_run: number;
  disabled: number;
  unverified: number;

  latest_success_at: string | null;
}

export interface SourceHealth {
  source_key: string;

  employer_name: string;
  source_type: string | null;
  ats: string;

  careers_url: string | null;

  enabled: boolean;
  source_verified: boolean;

  last_attempt_at: string | null;
  last_success_at: string | null;
  last_failure_at: string | null;

  last_raw_jobs: number;
  last_eligible_jobs: number;
  last_excluded_jobs: number;
  last_added_jobs: number;
  last_updated_jobs: number;
  last_disappeared_jobs: number;

  consecutive_failures: number;
  last_error: string | null;

  success_age_hours: number | null;
  runs_24h: number;
  failures_24h: number;

  health_status: SourceHealthStatus;
  health_reason: string;
}

export interface SourceRun {
  id: number;
  source_key: string;

  started_at: string;
  completed_at: string;

  success: boolean;

  raw_jobs: number;
  eligible_jobs: number;
  excluded_jobs: number;

  added_jobs: number;
  updated_jobs: number;
  disappeared_jobs: number;

  duration_ms: number | null;
  error_message: string | null;
}

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(
      `Source health API failed: ${response.status} ${response.statusText}`
    );
  }

  return response.json();
}

export async function fetchSourceHealthSummary(
  staleAfterHours = 24
): Promise<SourceHealthSummary> {
  const response = await fetch(
    `${API_BASE}/v80/admin/sources/summary?stale_after_hours=${staleAfterHours}`
  );

  return readJson<SourceHealthSummary>(response);
}

export async function fetchSourceHealth(
  staleAfterHours = 24
): Promise<SourceHealth[]> {
  const response = await fetch(
    `${API_BASE}/v80/admin/sources?stale_after_hours=${staleAfterHours}`
  );

  return readJson<SourceHealth[]>(response);
}

export async function fetchSourceRuns(
  sourceKey: string,
  limit = 20
): Promise<SourceRun[]> {
  const response = await fetch(
    `${API_BASE}/v80/admin/sources/${encodeURIComponent(
      sourceKey
    )}/runs?limit=${limit}`
  );

  return readJson<SourceRun[]>(response);
}
