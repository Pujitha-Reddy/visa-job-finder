import type { JobSort } from "./types";

type Props = {
  hours: number;
  setHours: (v: number) => void;
  query: string;
  setQuery: (v: string) => void;
  sourceType: string;
  setSourceType: (v: string) => void;
  applicationStatus: string;
  setApplicationStatus: (v: string) => void;
  experienceBand: string;
  setExperienceBand: (v: string) => void;
  sort: JobSort;
  setSort: (v: JobSort) => void;
  workArrangement: string;
  setWorkArrangement: (v: string) => void;
  agency: string;
  setAgency: (v: string) => void;
  employmentDetail: string;
  setEmploymentDetail: (v: string) => void;
  visaDetail: string;
  setVisaDetail: (v: string) => void;
};

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="filterField">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function UnifiedFilterPanel(p: Props) {
  return (
    <div className="filterStack">
      <label className="filterField">
        <span>Search</span>
        <input
          className="search"
          placeholder="Java, backend, Amazon..."
          value={p.query}
          onChange={(e) => p.setQuery(e.target.value)}
        />
      </label>

      <Select
        label="Posted"
        value={String(p.hours)}
        onChange={(v) => p.setHours(Number(v))}
        options={[
          { value: "24", label: "Last 24 hours" },
          { value: "72", label: "Last 3 days" },
        ]}
      />

      <Select
        label="Source"
        value={p.sourceType}
        onChange={p.setSourceType}
        options={[
          { value: "DIRECT_EMPLOYER", label: "Direct Employer" },
          { value: "", label: "All source types" },
          { value: "STARTUP", label: "Startup" },
          { value: "STAFFING_AGENCY", label: "Staffing Agency" },
          { value: "CONSULTING", label: "Consulting" },
        ]}
      />

      <Select
        label="Experience"
        value={p.experienceBand}
        onChange={p.setExperienceBand}
        options={[
          { value: "", label: "0–6 + Not Specified" },
          { value: "NEW_GRAD", label: "New Grad" },
          { value: "0-1", label: "0–1" },
          { value: "1-2", label: "1–2" },
          { value: "2-3", label: "2–3" },
          { value: "3-4", label: "3–4" },
          { value: "4-5", label: "4–5" },
          { value: "5-6", label: "5–6" },
          { value: "NOT_SPECIFIED", label: "Not Specified" },
        ]}
      />

      <Select
        label="Sort"
        value={p.sort}
        onChange={(v) => p.setSort(v as JobSort)}
        options={[
          { value: "best", label: "Best Match" },
          { value: "newest", label: "Newest" },
          { value: "sponsor", label: "Sponsor Strength" },
          { value: "experience", label: "Lowest YOE" },
          { value: "company", label: "Company" },
        ]}
      />

      <details className="moreFilters">
        <summary>More filters</summary>
        <div className="moreFiltersBody">
          <Select
            label="Work arrangement"
            value={p.workArrangement}
            onChange={p.setWorkArrangement}
            options={[
              { value: "", label: "All" },
              { value: "REMOTE", label: "Remote" },
              { value: "HYBRID", label: "Hybrid" },
              { value: "ONSITE", label: "Onsite" },
              { value: "UNKNOWN", label: "Needs review" },
            ]}
          />

          <Select
            label="Employment"
            value={p.employmentDetail}
            onChange={p.setEmploymentDetail}
            options={[
              { value: "", label: "All employment types" },
              { value: "FULL_TIME", label: "Full-Time" },
              { value: "CONTRACT_W2", label: "W2 Contract" },
              { value: "CONTRACT_C2C", label: "C2C" },
              { value: "CONTRACT_TO_HIRE", label: "Contract-to-Hire" },
              { value: "CONTRACT_UNKNOWN", label: "Contract — Review" },
            ]}
          />

          <Select
            label="Visa"
            value={p.visaDetail}
            onChange={p.setVisaDetail}
            options={[
              { value: "", label: "All visa statuses" },
              { value: "SPONSORSHIP_AVAILABLE", label: "Sponsorship Available" },
              { value: "F1_OPT_COMPATIBLE_SIGNAL", label: "F-1 / OPT Signal" },
              { value: "WORK_AUTHORIZATION_MENTIONED", label: "Work Authorization Mentioned" },
              { value: "NOT_MENTIONED", label: "Visa Not Mentioned — Review" },
              { value: "NO_SPONSORSHIP", label: "No Sponsorship" },
              { value: "RESTRICTED", label: "Restricted" },
            ]}
          />

          <Select
            label="Agency"
            value={p.agency}
            onChange={p.setAgency}
            options={[
              { value: "", label: "All agencies" },
              { value: "Insight Global", label: "Insight Global" },
              { value: "Randstad Digital", label: "Randstad Digital" },
              { value: "Robert Half", label: "Robert Half" },
            ]}
          />

          <Select
            label="Application status"
            value={p.applicationStatus}
            onChange={p.setApplicationStatus}
            options={[
              { value: "NEW", label: "New" },
              { value: "SAVED", label: "Saved" },
              { value: "APPLIED", label: "Applied" },
              { value: "INTERVIEW", label: "Interview" },
              { value: "REJECTED", label: "Rejected" },
              { value: "SKIPPED", label: "Skipped" },
              { value: "ALL", label: "All" },
            ]}
          />
        </div>
      </details>
    </div>
  );
}
