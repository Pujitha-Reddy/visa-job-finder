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
        label="Sponsor history"
        value={p.sourceType}
        onChange={p.setSourceType}
        options={[
          { value: "", label: "All sponsor-history levels" },
          { value: "STRONG", label: "Strong" },
          { value: "GOOD", label: "Good" },
          { value: "MODERATE", label: "Moderate" },
          { value: "WEAK", label: "Weak" },
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
            label="Visa"
            value={p.visaDetail}
            onChange={p.setVisaDetail}
            options={[
              { value: "", label: "All posting visa evidence" },
              { value: "EXPLICIT_SPONSORSHIP", label: "Explicit sponsorship" },
              { value: "POSSIBLE_SPONSORSHIP", label: "Possible sponsorship language" },
              { value: "NO_EXPLICIT_LANGUAGE", label: "No explicit visa language" },
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
