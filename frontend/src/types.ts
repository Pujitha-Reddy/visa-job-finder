export type Job = {
  id: number;
  company_name_raw: string;
  title: string;
  source: string;
  source_url: string;
  apply_url?: string | null;
  location_raw?: string | null;
  posted_at?: string | null;
  min_experience_years?: number | null;
  max_experience_years?: number | null;
  experience_text?: string | null;
  experience_match?: number | null;
  work_arrangement: "REMOTE" | "HYBRID" | "ONSITE" | "UNKNOWN";
  employment_type:
    | "FULL_TIME"
    | "CONTRACT_W2"
    | "CONTRACT_C2C"
    | "CONTRACT_UNKNOWN"
    | "TEMPORARY"
    | "INTERNSHIP"
    | "UNKNOWN";
  visa_language_status:
    | "SPONSORSHIP_AVAILABLE"
    | "OPT_F1_MENTIONED"
    | "NO_SPONSORSHIP"
    | "RESTRICTED"
    | "NOT_MENTIONED"
    | "UNKNOWN";
  h1b_history_strength: "STRONG" | "MEDIUM" | "LOW" | "UNKNOWN";
  sponsorship_score: number;
  overall_score: number;
  decision: "APPLY" | "OK_TO_APPLY" | "NEEDS_REVIEW" | "SKIP";
  decision_reason?: string | null;
  application_status: string;
};

export type Filters = {
  hours: 24 | 72;
  query: string;
  work: Set<string>;
  employment: Set<string>;
  visa: Set<string>;
  decision: Set<string>;
  applicationStatus: string;
};
