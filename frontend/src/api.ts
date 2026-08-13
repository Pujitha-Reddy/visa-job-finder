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
