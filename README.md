<h1 align="center">Visa Job Finder</h1>

<p align="center">
  <a href="https://visa-job-finder-ruby.vercel.app/">
    <b>🚀 Live Website</b>
  </a>
</p>

<p align="center">
  <!-- logos -->
</p>

<div align="center">

<img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
<img src="https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB" alt="React" />
<img src="https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript" />
<img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL" />
<img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite" />
<img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
<img src="https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white" alt="Vite" />
<img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
<img src="https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub" />
<img src="https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white" alt="GitHub Actions" />
<img src="https://img.shields.io/badge/AWS-232F3E?style=for-the-badge&logo=amazonwebservices&logoColor=white" alt="AWS" />
<img src="https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white" alt="Git" />


</div>


A production-oriented job discovery and prioritization platform for U.S. software engineering roles.

Visa Job Finder continuously collects jobs from employer career systems, normalizes them into a canonical job model, evaluates location and software-engineering relevance, enriches them with experience and sponsorship intelligence, ranks the resulting opportunities, and exposes them through a searchable web application.

The system is designed around one core principle:

> Find fresh, relevant U.S. software-engineering opportunities from primary employer sources and make sponsorship evidence, experience fit, and application state immediately actionable.


---

## Table of Contents

- [Overview](#overview)
- [Tech Stack & Architecture](#tech-stack-&-Architecture)
- [Why I Built This](#why-i-built-this)
- [Key Capabilities](#key-capabilities)
- [System Architecture](#system-architecture)
- [Production Architecture](#production-architecture)
- [Data Flow](#data-flow)
- [Employer and Source Registry](#employer-and-source-registry)
- [Job Ingestion](#job-ingestion)
- [Canonical Job Model](#canonical-job-model)
- [Job Lifecycle Management](#job-lifecycle-management)
- [Enrichment Pipeline](#enrichment-pipeline)
- [Sponsorship Intelligence](#sponsorship-intelligence)
- [Experience Matching](#experience-matching)
- [Eligibility and Location Filtering](#eligibility-and-location-filtering)
- [Ranking](#ranking)
- [Employer Discovery and Automatic Growth](#employer-discovery-and-automatic-growth)
- [Durable Cloud State](#durable-cloud-state)
- [Production Refresh Pipeline](#production-refresh-pipeline)
- [Health and Reliability](#health-and-reliability)
- [Backend API](#backend-api)
- [Frontend](#frontend)
- [Application Tracking](#application-tracking)
- [Filters and Search](#filters-and-search)
- [Technology Stack](#technology-stack)
- [Repository Structure](#repository-structure)
- [Local Development](#local-development)
- [Environment Variables](#environment-variables)
- [GitHub Actions](#github-actions)
- [Deployment](#deployment)
- [Production Validation](#production-validation)
- [Design Decisions](#design-decisions)
- [Engineering Challenges](#engineering-challenges)
- [Future Improvements](#future-improvements)
- [Project Status](#project-status)

---

# Overview

Visa Job Finder is a full-stack data and search platform built to improve the software-engineering job search for candidates who care about employer sponsorship history.

Traditional job boards combine stale postings, staffing agencies, duplicated listings, weak location data, and inconsistent sponsorship information.

This project takes a different approach.

It builds a source-backed job dataset directly from employer recruiting systems and transforms raw postings through a multi-stage data pipeline:

```text
Employer Universe
        ↓
Employer / ATS Discovery
        ↓
Verified Job Sources
        ↓
Job Collection
        ↓
Raw Job Observations
        ↓
Canonicalization
        ↓
Lifecycle Reconciliation
        ↓
Software Classification
        ↓
Location Enrichment
        ↓
Experience Enrichment
        ↓
Sponsorship Enrichment
        ↓
Eligibility
        ↓
Ranking
        ↓
PostgreSQL
        ↓
Backend API
        ↓
React Web Application
```

The result is a prioritized queue of fresh U.S. software-engineering jobs with structured evidence for:

- employer sponsorship history
- sponsorship language in the posting
- required experience
- work arrangement
- location eligibility
- employer source
- posting freshness
- application status
---

# Tech Stack & Architecture

**Frontend:** React, TypeScript, Vite, CSS  
**Backend:** Python, FastAPI, REST APIs  
**Data:** PostgreSQL, SQLite, SQL  
**Ingestion:** Greenhouse, Lever, Workday, Ashby, SmartRecruiters, Eightfold, ADP, Radancy  
**Cloud & DevOps:** GitHub Actions, Docker, AWS  
**Architecture:** Cloud-native ingestion, Canonical job pipeline, Employer/source discovery, Sponsorship enrichment, Eligibility filtering, Automated refresh & health monitoring

---

# Why I Built This

Searching for software-engineering jobs that are both relevant and realistically compatible with immigration requirements requires substantially more work than ordinary keyword search.

Important information is distributed across several independent systems:

- employer career websites
- Applicant Tracking Systems
- job descriptions
- historical sponsorship records
- company identity variations
- parent/subsidiary relationships
- location requirements
- experience requirements

A posting may never explicitly say that an employer has historically sponsored workers.

Likewise, a company with strong historical sponsorship activity may publish a particular role containing restrictive visa language.

Those are different signals and should not be collapsed into a single yes/no field.

Visa Job Finder therefore models job discovery as a data-engineering and information-retrieval problem rather than a simple scraper.

---

# Key Capabilities

The platform currently provides:

- Direct-employer job ingestion
- Multiple ATS integrations
- Canonical job normalization
- Duplicate-resistant observation storage
- Job lifecycle reconciliation
- U.S. location classification
- Software-engineering classification
- Experience requirement extraction
- Sponsorship-history intelligence
- Posting-level visa-language classification
- Job eligibility rules
- Multi-signal ranking
- Employer/source discovery
- Automatic bounded employer onboarding
- Persistent application tracking
- Source health monitoring
- Cloud-native scheduled refreshes
- PostgreSQL-backed durable state
- React/Vite web interface
- Production deployment independent of a developer workstation

---

# System Architecture

## High-Level Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│                    EMPLOYER UNIVERSE                         │
│                                                              │
│  Sponsor data + employer identities + known companies        │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│               EMPLOYER / SOURCE DISCOVERY                    │
│                                                              │
│  Career URLs → ATS detection → token/site resolution         │
│  → verification → source registry                            │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                       INGESTION                              │
│                                                              │
│  Greenhouse │ Lever │ Workday │ Ashby │ SmartRecruiters     │
│  Eightfold  │ ADP   │ Radancy │ Structured Web │ Generic    │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                    JOB OBSERVATIONS                          │
│                                                              │
│ Raw source-backed observations with provenance and timing    │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                  CANONICAL JOB LAYER                         │
│                                                              │
│ Normalize → resolve employer → deduplicate → reconcile        │
│ lifecycle → select best source                               │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                     ENRICHMENT                               │
│                                                              │
│ Software │ Location │ Experience │ Sponsorship │ Eligibility │
│ Ranking                                                      │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                    POSTGRESQL                                │
│                                                              │
│ Canonical jobs + enrichment + application state + registry   │
│ + source health + discovery/runtime state                    │
└──────────────────────┬───────────────────────┬───────────────┘
                       │                       │
                       ▼                       ▼
              ┌────────────────┐      ┌────────────────────┐
              │  Backend API   │      │ Production Refresh │
              │                │      │   GitHub Actions   │
              └───────┬────────┘      └────────────────────┘
                      │
                      ▼
              ┌────────────────┐
              │ React / Vite   │
              │   Frontend     │
              └────────────────┘
```

---

# Production Architecture

The production system is intentionally independent of a local machine.

```text
                        GitHub Repository
                               │
              ┌────────────────┴────────────────┐
              │                                 │
              ▼                                 ▼
       GitHub Actions                        Vercel
              │                                 │
              │                           React Frontend
              │                                 │
              ▼                                 │
     Ephemeral Linux Runner                     │
              │                                 │
      Hydrate cloud state                       │
              │                                 │
              ▼                                 │
       V112 Refresh                             │
              │                                 │
              ▼                                 │
    V114 Employer Growth                        │
              │                                 │
              ▼                                 │
       State Persistence                        │
              │                                 │
              └──────────────┐                  │
                             ▼                  │
                       PostgreSQL               │
                             ▲                  │
                             │                  │
                         Backend API ◄───────────┘
```

The developer laptop is not part of the production runtime.

GitHub Actions provides ephemeral compute.

PostgreSQL provides durable production state.

The web frontend consumes the production API and can be deployed independently.

---

# Data Flow

A production refresh follows this sequence:

```text
1. GitHub Actions starts a fresh Linux runner
2. Repository is checked out
3. Python dependencies are installed
4. Runtime SQLite state is hydrated from PostgreSQL
5. Verified employer sources are collected
6. Raw observations are normalized
7. Canonical jobs are reconciled
8. Lifecycle state is updated
9. Software classification runs
10. Location enrichment runs
11. Experience enrichment runs
12. Sponsorship enrichment runs
13. Eligibility is calculated
14. Ranking is calculated
15. Canonical state is synchronized to PostgreSQL
16. Bounded employer auto-onboarding runs when eligible
17. Updated employer/discovery state is persisted
18. Production health checks execute
```

This architecture lets SQLite serve as a fast ephemeral processing database while PostgreSQL remains the durable cloud system of record.

---

# Employer and Source Registry

The ingestion system separates an **employer** from a **job source**.

An employer represents the organization:

```text
Employer
├── canonical_name
├── display_name
├── website
├── careers_url
├── source_type
└── enabled
```

An employer may have one or more recruiting sources:

```text
Employer Source
├── employer_id
├── ats
├── token
├── careers_url
├── enabled
├── source_verified
├── last_checked_at
├── last_success_at
└── active_jobs
```

This distinction matters because large organizations can operate multiple recruiting systems, career sites, subsidiaries, or ATS instances.

Only verified/enabled sources participate in production collection.

---

# Job Ingestion

The ingestion layer is provider-aware.

Collectors include support for recruiting systems such as:

- Greenhouse
- Lever
- Workday
- Ashby
- SmartRecruiters
- Eightfold
- ADP
- Radancy
- structured web sources
- generic job-source adapters

The provider factory selects the appropriate transport based on the source registry.

Each ingestion attempt records operational information such as:

- source
- employer
- execution status
- raw jobs
- eligible jobs
- excluded jobs
- added jobs
- updated jobs
- disappeared jobs
- execution duration
- error information

This enables source-level observability rather than treating the entire collection process as a single opaque scraper.

---

# Canonical Job Model

Raw postings are not exposed directly to the product.

Every observation passes through a canonicalization layer.

The canonical model resolves multiple observations into a stable representation of the job.

Conceptually:

```text
Raw Source A ──┐
               │
Raw Source B ──┼──► Canonical Job
               │
Raw Source C ──┘
```

Canonicalization handles concerns such as:

- normalized title
- employer identity
- location
- posting URL
- source provenance
- first-seen time
- last-seen time
- active/inactive state
- source confidence
- deduplication
- lifecycle state

The separation between `job_observations` and `canonical_jobs` preserves provenance while giving the product a clean job entity.

---

# Job Lifecycle Management

Job postings change over time.

The system therefore tracks jobs as evolving entities instead of immutable scrape results.

Important lifecycle signals include:

```text
first_seen_at
last_seen_at
active
```

A job observed during repeated collection remains active.

When a previously observed job disappears from its verified source, lifecycle reconciliation can transition it away from the active feed while preserving historical and application information.

This allows the product to distinguish between:

- a currently available opportunity
- a previously seen posting
- a job the user already saved or applied to

Application history is therefore not destroyed simply because a source posting disappears.

---

# Enrichment Pipeline

Canonical jobs pass through independent enrichment stages.

```text
Canonical Job
     │
     ├──► Software Classification
     │
     ├──► Location Enrichment
     │
     ├──► Experience Enrichment
     │
     ├──► Sponsorship Enrichment
     │
     ├──► Eligibility
     │
     └──► Ranking
```

Keeping these stages separate makes the system easier to debug, re-run, and improve.

---

# Sponsorship Intelligence

Sponsorship is modeled using multiple independent signals.

## Employer Sponsorship History

The system maintains employer-level sponsorship history derived from sponsorship datasets and employer identity resolution.

The frontend exposes normalized sponsor-history bands such as:

```text
STRONG
GOOD
MODERATE
WEAK
```

This signal represents historical employer behavior.

It does **not** claim that a specific posting guarantees sponsorship.

## Posting-Level Visa Evidence

The text of an individual job posting is analyzed separately.

Posting-level evidence can be classified into states such as:

```text
EXPLICIT_SPONSORSHIP
POSSIBLE_SPONSORSHIP
NO_EXPLICIT_LANGUAGE
```

This distinction is deliberate.

For example:

```text
Employer historical sponsorship: STRONG
Posting visa evidence: NO_EXPLICIT_LANGUAGE
```

is fundamentally different from:

```text
Employer historical sponsorship: STRONG
Posting visa evidence: EXPLICIT_SPONSORSHIP
```

The product exposes both signals rather than presenting a misleading single "H-1B" badge.

---

# Experience Matching

Job descriptions frequently express experience requirements inconsistently.

Examples include:

```text
1+ years
2-3 years
minimum of 4 years
5 years of software development experience
new graduate
```

The experience enrichment layer converts these descriptions into structured experience bands.

The UI supports:

```text
New Grad
0–1
1–2
2–3
3–4
4–5
5–6
Not Specified
```

This allows users to prioritize jobs based on realistic experience fit rather than title alone.

---

# Eligibility and Location Filtering

The platform is focused on U.S. software-engineering opportunities.

Eligibility reconciliation combines multiple signals, including:

- software relevance
- geographic interpretation
- canonical lifecycle state
- source quality
- enrichment results

Location enrichment distinguishes work arrangements such as:

```text
REMOTE
HYBRID
ONSITE
UNKNOWN
```

The production health suite also checks for non-U.S. jobs leaking into the eligible U.S. feed.

---

# Ranking

Eligible jobs are prioritized rather than displayed as an unstructured chronological dump.

Ranking incorporates signals such as:

- experience fit
- sponsorship history
- posting-level sponsorship evidence
- freshness
- employer/source quality
- location/work arrangement
- canonical confidence

The frontend supports several ordering strategies:

```text
Best Match
Newest
Sponsor Strength
Lowest YOE
Company
```

The default experience is intended to answer:

> Which fresh jobs should I investigate first?

rather than merely:

> Which jobs were collected?

---

# Employer Discovery and Automatic Growth

The system is not limited to a permanently hard-coded employer list.

A discovery pipeline expands coverage using the sponsorship/employer universe.

Conceptually:

```text
Sponsor Universe
       ↓
Employer Identity Resolution
       ↓
Candidate Employer
       ↓
Career-Site Discovery
       ↓
ATS / Transport Detection
       ↓
Source Verification
       ↓
Employer Registry
       ↓
Production Collection
```

The project maintains a large combined sponsor/employer universe and processes promising candidates through discovery batches.

Automatic onboarding is deliberately bounded.

A production run can limit:

```text
batch candidates
discovery attempts
verification attempts
minimum interval between growth runs
```

This prevents uncontrolled source expansion during ordinary production refreshes.

A representative production invocation is:

```bash
python -u -m app.run_employer_auto_onboarding \
  --create-batch \
  --batch-limit 25 \
  --discovery-limit 5 \
  --verification-limit 5 \
  --min-interval-hours 24
```

Employer growth is therefore incremental, observable, and rate-controlled.

---

# Durable Cloud State

A major architectural requirement was eliminating dependence on a developer workstation.

Earlier iterations accumulated important runtime state in SQLite.

For production, durable state was migrated to PostgreSQL.

Persistent cloud state includes areas such as:

- employer registry
- employer sources
- employer identities
- sponsor universe
- source discovery batches
- canonical jobs
- canonical enrichment
- canonical sources
- job observations
- application state
- source health
- source run history
- employer-onboarding runtime state

The cloud runner hydrates the state required for processing into an ephemeral SQLite database.

After processing, durable changes are synchronized back to PostgreSQL.

```text
              START RUN
                  │
                  ▼
             PostgreSQL
                  │
                  │ hydrate
                  ▼
          Ephemeral SQLite
                  │
                  │ process
                  ▼
       Collection / Enrichment
                  │
                  │ persist
                  ▼
             PostgreSQL
                  │
                  ▼
               END RUN
```

The ephemeral database can disappear with the GitHub runner without losing production state.

---

# Production Refresh Pipeline

The canonical refresh pipeline is orchestrated by:

```text
app.run_v112_refresh_pipeline
```

The cloud workflow performs:

```text
Hydration
    ↓
V112 canonical refresh
    ↓
V114 bounded employer onboarding
    ↓
Runtime-state persistence
    ↓
V113 production health
```

The workflow uses a concurrency group so multiple production refreshes do not overlap.

---

# Health and Reliability

Production health is treated as a first-class system component.

The V113 health layer checks areas including:

```text
Scheduler / execution environment
Ingestion coverage
Persistent source failures
Canonical data
U.S. eligibility integrity
SQLite ↔ PostgreSQL parity when applicable
```

Source health is persisted independently from individual ingestion attempts.

A source can therefore maintain operational information such as:

```text
last_attempt_at
last_success_at
last_failure_at
consecutive_failures
last_error
```

while individual execution history is retained separately.

This avoids confusing a transient failed attempt with a permanently unhealthy production source.

A healthy run requires the critical data-quality invariants to pass.

Example:

```text
OVERALL: HEALTHY

INGESTION
  sources: 162/162
  statuses: {'SUCCESS': 162}
  persistent failures: 0

CHECKS
  PASS | scheduler_last_exit_ok
  PASS | all_sources_have_runs
  PASS | no_persistent_failures
  PASS | zero_non_us_eligible_leaks
  PASS | parity
```

---

# Backend API

The backend is implemented in Python and FastAPI.

The current product API is built around the canonical V110 job feed.

Responsibilities include:

- canonical job retrieval
- filtering
- sorting
- application-state updates
- source-health information
- canonical sponsorship fields
- canonical posting evidence

The API reads production data from PostgreSQL when configured for cloud execution.

---

# Frontend

The frontend is built with:

- React
- TypeScript
- Vite

The application presents a prioritized job-search workspace rather than a generic job-board interface.

Primary views include:

```text
Fresh jobs
Saved
Applied
Interviews
Source Health
```

The job cards expose decision-relevant information including:

- title
- employer
- source
- location
- work arrangement
- sponsor-history strength
- posting-level visa evidence
- experience requirement
- freshness
- application controls
- direct application link

---

# Application Tracking

Application state is stored separately from posting lifecycle.

Supported states include:

```text
NEW
SAVED
APPLIED
INTERVIEW
REJECTED
SKIPPED
```

When a job is marked `APPLIED`, the system records its application timestamp.

Application history is preserved even if the original posting later closes.

This separation prevents source lifecycle reconciliation from destroying user workflow state.

---

# Filters and Search

The product provides filters for:

## Freshness

```text
Last 24 hours
Last 3 days
```

## Sponsor History

```text
All sponsor-history levels
Strong
Good
Moderate
Weak
```

## Experience

```text
0–6 + Not Specified
New Grad
0–1
1–2
2–3
3–4
4–5
5–6
Not Specified
```

## Work Arrangement

```text
All
Remote
Hybrid
Onsite
Needs review
```

## Posting Visa Evidence

```text
All posting visa evidence
Explicit sponsorship
Possible sponsorship language
No explicit visa language
```

## Application Status

```text
New
Saved
Applied
Interview
Rejected
Skipped
All
```

## Sorting

```text
Best Match
Newest
Sponsor Strength
Lowest YOE
Company
```

Free-text search can be used for titles, technologies, employers, and other indexed job information.

---

# Technology Stack

## Backend

| Technology | Purpose |
|---|---|
| Python | Pipeline and backend implementation |
| FastAPI | HTTP API |
| SQLite | Ephemeral/local pipeline processing |
| PostgreSQL | Durable production datastore |
| psycopg | PostgreSQL connectivity |

## Frontend

| Technology | Purpose |
|---|---|
| React | User interface |
| TypeScript | Type-safe frontend development |
| Vite | Development/build tooling |

## Data / Ingestion

| Component | Purpose |
|---|---|
| ATS-specific collectors | Primary employer job collection |
| Canonicalization | Normalize heterogeneous postings |
| Employer identity graph | Resolve company aliases and relationships |
| Sponsorship datasets | Employer sponsorship intelligence |
| Enrichment pipeline | Structured job attributes |
| Lifecycle reconciliation | Active/inactive posting management |

## Infrastructure

| Technology | Purpose |
|---|---|
| GitHub | Source control |
| GitHub Actions | Cloud production execution |
| PostgreSQL / Supabase-compatible database | Durable cloud state |
| Vercel | Frontend deployment |

---

# Repository Structure

```text
visa-job-finder/
│
├── .github/
│   └── workflows/
│       └── daily-jobs.yml
│
├── backend/
│   ├── app/
│   │   ├── collectors/
│   │   │   ├── greenhouse.py
│   │   │   ├── lever.py
│   │   │   ├── workday.py
│   │   │   ├── ashby.py
│   │   │   ├── smartrecruiters.py
│   │   │   ├── eightfold.py
│   │   │   ├── adp.py
│   │   │   ├── radancy.py
│   │   │   └── generic_jobs.py
│   │   │
│   │   ├── ingestion/
│   │   │   ├── providers/
│   │   │   ├── canonical_normalize.py
│   │   │   ├── canonical_repository.py
│   │   │   ├── employer_resolver.py
│   │   │   ├── lifecycle.py
│   │   │   ├── models.py
│   │   │   └── repository.py
│   │   │
│   │   ├── canonical_db.py
│   │   ├── canonicalize_job_observations.py
│   │   │
│   │   ├── enrichment_software.py
│   │   ├── enrichment_location.py
│   │   ├── enrichment_experience.py
│   │   ├── enrichment_sponsorship.py
│   │   ├── enrichment_eligibility.py
│   │   ├── enrichment_ranking.py
│   │   │
│   │   ├── discover_employer_careers.py
│   │   ├── source_discovery_engine.py
│   │   ├── verify_auto_discovered_sources.py
│   │   ├── run_employer_auto_onboarding.py
│   │   │
│   │   ├── bootstrap_v119_cloud_runner.py
│   │   ├── sync_v119_runtime_state_to_postgres.py
│   │   │
│   │   ├── run_v112_refresh_pipeline.py
│   │   ├── run_v113_health.py
│   │   │
│   │   ├── v110_routes.py
│   │   ├── v113_routes.py
│   │   └── main.py
│   │
│   ├── requirements.txt
│   └── data/
│
├── config/
│   └── v119_runner_schema.sql
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── UnifiedFilterPanel.tsx
│   │   ├── api_v110.ts
│   │   └── types.ts
│   ├── package.json
│   └── vite.config.ts
│
├── .gitignore
└── README.md
```

The repository also contains migration, discovery, reconciliation, and diagnostic utilities used during the evolution of the data platform.

---

# Local Development

## Prerequisites

Recommended tools:

```text
Python 3.13
Node.js
npm
PostgreSQL access
```

## Backend

```bash
cd backend

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

Start the API:

```bash
python -m uvicorn app.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --reload
```

The local API is then available at:

```text
http://127.0.0.1:8000
```

## Frontend

```bash
cd frontend

npm install
npm run dev
```

Vite normally exposes the development application at:

```text
http://localhost:5173
```

## Production Build

```bash
cd frontend
npm run build
```

The build performs TypeScript compilation followed by the Vite production build.

---

# Environment Variables

The production system expects a PostgreSQL connection string:

```bash
DATABASE_URL=...
```

The frontend supports an API base URL through variables such as:

```bash
VITE_API_BASE_URL=...
```

The application also retains compatibility with:

```bash
VITE_API_BASE=...
```

Do not commit production credentials or `.env` files to source control.

---

# GitHub Actions

Production collection runs in GitHub Actions rather than on a developer workstation.

The workflow:

```text
.github/workflows/daily-jobs.yml
```

performs the cloud refresh.

Core workflow:

```yaml
- Checkout repository
- Set up Python
- Install backend dependencies
- Hydrate fresh runner from PostgreSQL
- Run canonical V112 refresh
- Run bounded employer auto-onboarding
- Persist employer growth state to PostgreSQL
- Run production health checks
```

A representative hydration step:

```bash
rm -f data/jobs.db
python -u -m app.bootstrap_v119_cloud_runner
```

Canonical refresh:

```bash
python -u -m app.run_v112_refresh_pipeline
```

Employer growth:

```bash
python -u -m app.run_employer_auto_onboarding \
  --create-batch \
  --batch-limit 25 \
  --discovery-limit 5 \
  --verification-limit 5 \
  --min-interval-hours 24
```

State persistence:

```bash
python -u -m app.sync_v119_runtime_state_to_postgres
```

Production validation:

```bash
python -u -m app.run_v113_health
```

The workflow uses:

```yaml
concurrency:
  group: visa-job-finder-production-refresh
  cancel-in-progress: false
```

to prevent overlapping production refreshes.

---

# Deployment

## Frontend

The React application is deployed through Vercel.

The deployment is connected to the GitHub repository, allowing frontend changes pushed to the production branch to trigger a new deployment.

## Backend Data

The production data layer is PostgreSQL.

The database stores canonical jobs and the durable state required for the next cloud execution.

## Pipeline Compute

GitHub Actions provides the compute environment for collection, canonicalization, enrichment, discovery, synchronization, and health validation.

Therefore:

```text
GitHub
   │
   ├──► Vercel → Frontend
   │
   └──► GitHub Actions
             │
             ▼
       Processing Pipeline
             │
             ▼
         PostgreSQL
             │
             ▼
         Backend API
             │
             ▼
          Frontend
```

No always-on developer laptop is required for production refreshes.

---

# Production Validation

The project includes several layers of validation.

## Compilation

Python production modules are compile-checked before release.

## Frontend Build

```bash
npm run build
```

validates TypeScript and creates the production Vite bundle.

## API Contract

Canonical API queries are tested across important product scenarios, including:

```text
default feed
software-engineer search
Java search
remote jobs
strong sponsor history
possible sponsorship language
all application states
```

## Data Integrity

Health checks verify invariants including:

```text
all enabled sources have runs
no persistent source failures
zero non-U.S. eligible leaks
canonical database consistency
SQLite/PostgreSQL parity when applicable
```

## Cloud Runner Hydration

A clean runner can reconstruct required runtime state from PostgreSQL without relying on a pre-existing local database.

This was explicitly validated by deleting the runtime SQLite database, hydrating from PostgreSQL, and comparing the reconstructed state with expected production counts.

---

# Design Decisions

## 1. Primary Employer Sources Over Aggregators

The system prioritizes employer-controlled recruiting sources.

This improves provenance and reduces dependence on duplicated or stale aggregator listings.

---

## 2. Observations and Canonical Jobs Are Separate

A scraped job is an observation.

A product-visible job is a canonical entity.

Keeping these separate preserves source provenance and makes lifecycle reconciliation possible.

---

## 3. Sponsorship History and Posting Language Are Separate Signals

Historical sponsorship does not guarantee sponsorship for an individual role.

Posting language does not fully describe an employer's historical behavior.

The platform therefore models both.

---

## 4. PostgreSQL Is the Durable Production System

GitHub runners are ephemeral.

SQLite is useful for local and transient processing, but production state must survive runner destruction.

PostgreSQL therefore stores durable state while the cloud runner reconstructs its working database as needed.

---

## 5. Employer Growth Is Bounded

Automatic source discovery can create uncontrolled network activity and unreliable sources if allowed to expand without limits.

The onboarding pipeline therefore uses explicit limits and cooldowns.

---

## 6. Application State Is Independent of Posting State

A closed job may still be important because the user applied to it.

Application state is therefore persisted independently from source availability.

---

## 7. Health Checks Validate Invariants, Not Just Process Exit

A pipeline returning exit code zero does not guarantee good data.

Production health additionally evaluates source coverage, persistent failures, geographic integrity, and data consistency.

---

# Engineering Challenges

Building the platform required solving several problems beyond basic web scraping.

## Heterogeneous ATS Systems

Different recruiting platforms expose jobs through very different APIs, identifiers, pagination strategies, and location formats.

The collector layer abstracts these differences behind a common ingestion model.

## Employer Identity Resolution

Sponsorship records and career systems frequently use different company names.

Identity resolution is necessary to connect historical sponsorship evidence to the correct recruiting entity.

## Parent and Subsidiary Relationships

Large employers can operate through multiple legal entities and recruiting systems.

The sponsorship universe and identity graph help reconcile those relationships.

## Canonicalization

The same underlying opportunity may appear through multiple observations or change over time.

A canonical layer prevents the UI from behaving like a raw scrape database.

## Job Lifecycle

Freshness cannot be modeled solely using a posting timestamp.

Repeated source observations are used to maintain first-seen, last-seen, and active state.

## Cloud Migration

The processing architecture originally depended heavily on local SQLite state.

Moving execution to ephemeral GitHub runners required identifying which state was durable, migrating that state to PostgreSQL, creating a reproducible SQLite schema, implementing hydration, and synchronizing state back to the cloud.

## Reliable Health Classification

Individual ingestion attempts and persistent source health are different concepts.

Production monitoring separates historical run events from durable source-health state so transient failures do not incorrectly represent long-term source health.

---

# Future Improvements

Potential next steps include:

- Increase verified direct-employer coverage
- Continue automatic sponsor-driven employer discovery
- Improve employer/subsidiary identity resolution
- Expand structured sponsorship evidence
- Improve salary extraction and normalization
- Add richer skill extraction
- Add personalized ranking weights
- Add application analytics
- Add interview and follow-up reminders
- Add recruiter/contact workflow support
- Improve source-health dashboards
- Add automated regression tests around pipeline invariants
- Add richer production observability
- Reduce legacy migration/diagnostic code as the architecture stabilizes

---

# Project Status

The current production architecture includes:

```text
✓ Multi-ATS employer ingestion
✓ Canonical observation/job architecture
✓ Job lifecycle reconciliation
✓ Software classification
✓ U.S. location enrichment
✓ Experience enrichment
✓ Sponsorship-history enrichment
✓ Posting-level visa evidence
✓ Eligibility reconciliation
✓ Multi-signal ranking
✓ Persistent application tracking
✓ Employer/source discovery
✓ Bounded automatic employer onboarding
✓ PostgreSQL durable cloud state
✓ Fresh-runner hydration
✓ Runtime-state persistence
✓ Production source-health monitoring
✓ React/TypeScript frontend
✓ GitHub Actions cloud execution
✓ Vercel frontend deployment
✓ Production health validation
```

The production pipeline is designed to run independently of a developer workstation.

---

# Architecture Summary

```text
                         VISA JOB FINDER
                               │
             ┌─────────────────┴─────────────────┐
             │                                   │
             ▼                                   ▼
      SPONSOR INTELLIGENCE                EMPLOYER SOURCES
             │                                   │
             │                          ┌────────┼────────┐
             │                          │        │        │
             │                       Workday  Greenhouse Lever ...
             │                          │        │        │
             └──────────────┐           └────┬───┴────────┘
                            │                │
                            ▼                ▼
                     EMPLOYER IDENTITY   INGESTION
                            │                │
                            └────────┬───────┘
                                     ▼
                              JOB OBSERVATIONS
                                     │
                                     ▼
                               CANONICALIZATION
                                     │
                                     ▼
                           LIFECYCLE RECONCILIATION
                                     │
                                     ▼
                  ┌──────────────────────────────────┐
                  │          ENRICHMENT              │
                  │                                  │
                  │ Software       Location          │
                  │ Experience     Sponsorship       │
                  │ Eligibility    Ranking           │
                  └────────────────┬─────────────────┘
                                   │
                                   ▼
                              POSTGRESQL
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
                FASTAPI                     CLOUD STATE
                    │                             ▲
                    ▼                             │
              REACT / VITE                 GITHUB ACTIONS
                    │                             │
                    ▼                             │
                 VERCEL                           │
                    │                             │
                    └──────── PRODUCTION ─────────┘
```

---

## Author

**Pujitha Malladi**

Full-Stack Software Engineer

Built as an end-to-end software, data, automation, and cloud engineering project focused on making the U.S. software-engineering job search more structured, evidence-based, and actionable.

## License

Copyright © 2026 Pujitha Malladi. All rights reserved.