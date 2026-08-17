export type Job = {
  id: number;
  company_name_raw: string;
  title: string;
  source: string;
  source_url: string;
  apply_url?: string | null;
  source_type?: string | null;
  agency_name?: string | null;
  location_raw?: string | null;
  posted_at?: string | null;
  source_published_at?: string | null;
  effective_posted_at?: string | null;
  freshness_confidence?: string | null;
  freshness_source?: string | null;
  min_experience_years?: number | null;
  max_experience_years?: number | null;
  experience_text?: string | null;
  experience_match?: number | null;
  experience_band?: string | null;
  work_arrangement: "REMOTE" | "HYBRID" | "ONSITE" | "UNKNOWN";
  employment_type:
    | "FULL_TIME"
    | "CONTRACT_W2"
    | "CONTRACT_C2C"
    | "CONTRACT_UNKNOWN"
    | "TEMPORARY"
    | "INTERNSHIP"
    | "UNKNOWN";
  employment_detail_type?: string | null;
  visa_language_status:
    | "SPONSORSHIP_AVAILABLE"
    | "OPT_F1_MENTIONED"
    | "NO_SPONSORSHIP"
    | "RESTRICTED"
    | "NOT_MENTIONED"
    | "UNKNOWN";
  visa_detail_status?: string | null;
  visa_evidence_text?: string | null;
  h1b_history_strength: "STRONG" | "MEDIUM" | "LOW" | "UNKNOWN";
  sponsorship_score: number;
  overall_score: number;
  source_confidence_score?: number | null;
  source_confidence_label?: string | null;
  decision: "APPLY" | "OK_TO_APPLY" | "NEEDS_REVIEW" | "SKIP";
  decision_reason?: string | null;
  application_status:
    | "NEW"
    | "SAVED"
    | "APPLIED"
    | "INTERVIEW"
    | "REJECTED"
    | "SKIPPED";
  date_applied?: string | null;
  is_active?: boolean | null;
  last_verified_at?: string | null;
  disappeared_at?: string | null;
};

export type Filters = {
  hours: 24 | 72;
  query: string;
  applicationStatus: string;
};

export type JobSort =
  | "best"
  | "newest"
  | "sponsor"
  | "experience"
  | "company";
