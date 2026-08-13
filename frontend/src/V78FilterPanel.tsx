type Option = { value: string; label?: string };

type Props = {
  sourceType: string;
  setSourceType: (v: string) => void;
  agency: string;
  setAgency: (v: string) => void;
  employment: string;
  setEmployment: (v: string) => void;
  visa: string;
  setVisa: (v: string) => void;
  experience: string;
  setExperience: (v: string) => void;
};

const sourceTypes: Option[] = [
  { value: "", label: "All source types" },
  { value: "DIRECT_EMPLOYER", label: "Direct Employer" },
  { value: "STARTUP", label: "Startup" },
  { value: "STAFFING_AGENCY", label: "Staffing Agency" },
  { value: "CONSULTING", label: "Consulting" },
];

const agencies: Option[] = [
  { value: "", label: "All agencies" },
  { value: "Insight Global" },
  { value: "Randstad Digital" },
  { value: "Robert Half" },
  { value: "Kforce" },
  { value: "TEKsystems" },
];

const employmentTypes: Option[] = [
  { value: "", label: "All employment types" },
  { value: "FULL_TIME", label: "Full-Time" },
  { value: "CONTRACT_W2", label: "W2 Contract" },
  { value: "CONTRACT_C2C", label: "C2C" },
  { value: "CONTRACT_TO_HIRE", label: "Contract-to-Hire" },
  { value: "CONTRACT_UNKNOWN", label: "Contract — Review" },
];

const visaTypes: Option[] = [
  { value: "", label: "All visa statuses" },
  { value: "SPONSORSHIP_AVAILABLE", label: "Sponsorship Available" },
  { value: "F1_OPT_COMPATIBLE_SIGNAL", label: "F-1 / OPT Signal" },
  { value: "WORK_AUTHORIZATION_MENTIONED", label: "Work Authorization Mentioned" },
  { value: "NOT_MENTIONED", label: "Visa Not Mentioned — Review" },
  { value: "NO_SPONSORSHIP", label: "No Sponsorship" },
  { value: "RESTRICTED", label: "Restricted" },
];

const experienceBands: Option[] = [
  { value: "", label: "0–6 + Not Specified" },
  { value: "NEW_GRAD", label: "New Grad" },
  { value: "0-1" },
  { value: "1-2" },
  { value: "2-3" },
  { value: "3-4" },
  { value: "4-5" },
  { value: "5-6" },
  { value: "6+" },
  { value: "NOT_SPECIFIED", label: "Not Specified" },
];

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Option[];
}) {
  return (
    <label className="v78-filter">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label || o.value}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function V78FilterPanel(props: Props) {
  return (
    <div className="v78-filter-grid">
      <Select label="Source Type" value={props.sourceType} onChange={props.setSourceType} options={sourceTypes} />
      <Select label="Agency" value={props.agency} onChange={props.setAgency} options={agencies} />
      <Select label="Employment" value={props.employment} onChange={props.setEmployment} options={employmentTypes} />
      <Select label="Visa" value={props.visa} onChange={props.setVisa} options={visaTypes} />
      <Select label="Experience" value={props.experience} onChange={props.setExperience} options={experienceBands} />
    </div>
  );
}
