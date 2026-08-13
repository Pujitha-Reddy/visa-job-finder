# Visa Job Finder

A personal job-search automation that discovers software engineering jobs, classifies work arrangement and employment type, checks visa/sponsorship language, stores H-1B sponsor-history signals separately, and ranks jobs for review.

## Version 1 requirements

- Target roles:
  - Software Engineer
  - Full Stack Engineer
  - Backend Engineer
  - Frontend Engineer
  - Java Developer
  - Java Software Engineer
- Experience: New Grad / 0 YOE through 6 YOE
- Work arrangement:
  - Remote = Preferred
  - Hybrid = OK to Apply
  - Onsite = Needs Review
- Posting age filters:
  - Last 24 hours
  - Last 3 days
- Employment filters:
  - Full-Time
  - Contract
  - W2
  - C2C
  - Unknown
- Visa logic:
  - Explicit sponsorship support = positive evidence
  - Explicit no-sponsorship = reject/skip signal
  - No visa language = Needs Review, NOT rejection
  - H-1B employer history is stored separately from job-specific sponsorship evidence

## Architecture

Frontend (React/TypeScript later)
        |
        v
FastAPI API
        |
        v
SQLite
        |
        +--> Job collectors (Greenhouse / Lever / company sites)
        +--> Visa analyzer
        +--> Experience parser
        +--> Work-arrangement classifier
        +--> Sponsor-history database (DOL / USCIS)

## Run backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:

- API health: http://127.0.0.1:8000/health
- Swagger: http://127.0.0.1:8000/docs

## Next milestone

1. Add Greenhouse collector
2. Add Lever collector
3. Add title/experience/location parsers
4. Add visa-language analyzer
5. Populate sponsor-history tables from DOL/USCIS
6. Build React dashboard
7. Add GitHub Actions daily run


## Milestone 2: Greenhouse + Lever collectors

The project now contains public ATS collectors for Greenhouse and Lever.

Configure employers in:

```text
config/companies.yaml
```

Then run:

```bash
cd backend
python -m app.collect
```

The collector:
- fetches public ATS postings
- keeps target software-engineering titles by default
- normalizes Greenhouse/Lever records into one job shape
- deduplicates by source URL
- inserts/updates SQLite
- exposes a manual `POST /collect` FastAPI endpoint

No employers are preconfigured by default. Add only boards you want to monitor.


## Milestone 3: H-1B sponsor intelligence

The project now supports employer-level sponsorship history.

### Official evidence layers

- DOL LCA disclosure data: historical LCA filing/certification evidence.
- USCIS H-1B Employer Data Hub files: historical employer petition evidence.
- Current job description: job-specific visa/sponsorship evidence.

Historical evidence does **not** prove that a particular current job will sponsor.

### Import downloaded official CSV files

DOL:

```bash
cd backend
python -m app.import_sponsors --dol /path/to/dol_lca.csv --year 2026
```

USCIS:

```bash
python -m app.import_sponsors --uscis /path/to/uscis_h1b.csv --year 2025
```

Recalculate sponsor history for all stored jobs:

```bash
python -m app.import_sponsors --enrich
```

API:

```text
GET  /sponsors/{company_name}
POST /sponsors/enrich
```

### Conservative decision rule

If the job does not mention visa sponsorship:

- Strong employer history -> NEEDS REVIEW — STRONG SPONSOR HISTORY
- Medium history -> NEEDS REVIEW — MEDIUM SPONSOR HISTORY
- Weak/unknown history -> NEEDS REVIEW

If the current job explicitly says no sponsorship, historical sponsorship does not override it.


## Milestone 4: React dashboard

The frontend now includes:

- Search box
- Last 24 hours / Last 3 days
- Remote / Hybrid / Onsite / Unknown filters
- Full-Time / W2 / C2C / Contract filters
- Sponsorship / OPT-F1 / Needs Review filters
- Apply / OK to Apply / Needs Review / Skip filters
- Job cards showing sponsor history and visa evidence
- Direct application link

Run backend:

```bash
cd backend
uvicorn app.main:app --reload
```

Run frontend in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Then open:

```text
http://localhost:5173
```

The frontend expects the API at `http://127.0.0.1:8000` by default.

To use another backend URL, create `frontend/.env`:

```text
VITE_API_BASE=https://your-api.example.com
```
