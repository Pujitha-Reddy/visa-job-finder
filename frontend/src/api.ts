import type { Job } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export async function fetchJobs(hours: number, applicationStatus = "NEW"): Promise<Job[]> {
  const params = new URLSearchParams({ hours: String(hours), application_status: applicationStatus });
  const res = await fetch(`${API_BASE}/jobs?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load jobs: ${res.status}`);
  return res.json();
}

export async function fetchStats(hours: number) {
  const res = await fetch(`${API_BASE}/stats?hours=${hours}`);
  if (!res.ok) throw new Error(`Failed to load stats: ${res.status}`);
  return res.json();
}

export async function updateJobStatus(jobId: number, status: string): Promise<Job> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error(`Failed to update job status: ${res.status}`);
  return res.json();
}

export async function fetchV78Jobs(params: {
  hours: number;
  sourceType?: string;
  agency?: string;
  employmentDetail?: string;
  visaDetail?: string;
  experienceBand?: string;
  workArrangement?: string;
  applicationStatus?: string;
}) {
  const search = new URLSearchParams();

  search.set("hours", String(params.hours));

  if (params.sourceType) {
    search.set("source_type", params.sourceType);
  }

  if (params.agency) {
    search.set("agency", params.agency);
  }

  if (params.employmentDetail) {
    search.set("employment_detail_type", params.employmentDetail);
  }

  if (params.visaDetail) {
    search.set("visa_detail_status", params.visaDetail);
  }

  if (params.experienceBand) {
    search.set("experience_band", params.experienceBand);
  }

  if (params.workArrangement) {
    search.set("work_arrangement", params.workArrangement);
  }

  search.set(
    "application_status",
    params.applicationStatus || "NEW"
  );

  const response = await fetch(
    `http://127.0.0.1:8000/v78/jobs?${search.toString()}`
  );

  if (!response.ok) {
    throw new Error(`Failed to load jobs: ${response.status}`);
  }

  return response.json();
}