const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

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
  if (params.sourceType) search.set("source_type", params.sourceType);
  if (params.agency) search.set("agency", params.agency);
  if (params.employmentDetail) search.set("employment_detail_type", params.employmentDetail);
  if (params.visaDetail) search.set("visa_detail_status", params.visaDetail);
  if (params.experienceBand) search.set("experience_band", params.experienceBand);
  if (params.workArrangement) search.set("work_arrangement", params.workArrangement);
  search.set("application_status", params.applicationStatus || "NEW");

  const r = await fetch(`${API_BASE}/v80/jobs?${search.toString()}`);
  if (!r.ok) throw new Error(`Failed to load jobs from Supabase: ${r.status}`);
  return r.json();
}

export async function fetchStats(hours: number) {
  const r = await fetch(`${API_BASE}/v80/stats?hours=${hours}`);
  if (!r.ok) throw new Error(`Failed to load Supabase stats: ${r.status}`);
  return r.json();
}

export async function updateJobStatus(jobId: number, status: string) {
  const r = await fetch(`${API_BASE}/v80/jobs/${jobId}/status`, {
    method: "PATCH",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({status}),
  });
  if (!r.ok) throw new Error(`Failed to update job status: ${r.status}`);
  return r.json();
}
