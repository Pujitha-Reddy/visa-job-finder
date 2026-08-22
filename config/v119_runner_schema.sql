-- V119 certified ephemeral-runner SQLite schema
-- Generated from the production-accepted jobs.db.
--
-- DATA IS NOT INCLUDED.
-- GitHub Actions creates an empty SQLite runtime database from
-- this schema and hydrates durable production state from Postgres.

PRAGMA foreign_keys = OFF;

CREATE TABLE canonical_job_enrichment (
                canonical_job_id INTEGER PRIMARY KEY,

                -- ------------------------------------------
                -- Software-role classification
                -- ------------------------------------------
                is_software_role INTEGER,
                software_role_family TEXT,
                software_role_score REAL,
                software_role_reason TEXT,

                -- ------------------------------------------
                -- Location
                -- ------------------------------------------
                country_code TEXT,
                state_code TEXT,
                city TEXT,

                work_arrangement TEXT,

                is_us_job INTEGER,
                is_us_remote INTEGER,

                location_confidence REAL,
                location_reason TEXT,

                -- ------------------------------------------
                -- Experience
                -- ------------------------------------------
                min_experience_years REAL,
                max_experience_years REAL,

                seniority_band TEXT,
                experience_confidence REAL,
                experience_reason TEXT,

                -- ------------------------------------------
                -- Sponsorship
                -- ------------------------------------------
                sponsor_parent_key TEXT,

                sponsor_history_strength TEXT,
                sponsor_recent_filings INTEGER,
                sponsor_recent_approvals INTEGER,

                visa_language_status TEXT,
                visa_language_evidence TEXT,

                sponsorship_score REAL,
                sponsorship_reason TEXT,

                -- ------------------------------------------
                -- Eligibility
                -- ------------------------------------------
                is_eligible INTEGER,

                eligibility_reason TEXT,
                location_eligibility TEXT,
                experience_eligibility TEXT,
                sponsorship_eligibility TEXT,

                -- ------------------------------------------
                -- Ranking
                -- ------------------------------------------
                relevance_score REAL,
                freshness_score REAL,
                source_quality_score REAL,
                overall_score REAL,

                -- ------------------------------------------
                -- Processing
                -- ------------------------------------------
                enrichment_version TEXT NOT NULL
                    DEFAULT 'V109',

                enriched_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(canonical_job_id)
                    REFERENCES canonical_jobs(id)
            );

CREATE TABLE canonical_job_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                canonical_job_id INTEGER NOT NULL,
                observation_id INTEGER NOT NULL UNIQUE,

                provider TEXT NOT NULL,

                source_confidence REAL
                    NOT NULL DEFAULT 0,

                match_method TEXT NOT NULL,

                match_confidence REAL
                    NOT NULL DEFAULT 0,

                first_seen_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                last_seen_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                is_active INTEGER NOT NULL DEFAULT 1,

                FOREIGN KEY(
                    canonical_job_id
                )
                REFERENCES canonical_jobs(id),

                FOREIGN KEY(
                    observation_id
                )
                REFERENCES job_observations(id)
            );

CREATE TABLE canonical_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                canonical_key TEXT NOT NULL UNIQUE,

                employer_identity_id INTEGER NOT NULL,

                canonical_title TEXT NOT NULL,
                canonical_location TEXT,

                description TEXT,

                preferred_source_url TEXT,
                preferred_apply_url TEXT,

                external_id TEXT,

                posted_at TEXT,

                first_seen_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                last_seen_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                is_active INTEGER NOT NULL DEFAULT 1,

                source_count INTEGER NOT NULL DEFAULT 1,

                best_source_confidence REAL
                    NOT NULL DEFAULT 0,

                canonicalization_confidence REAL
                    NOT NULL DEFAULT 0,

                freshness_status TEXT
                    NOT NULL DEFAULT 'CURRENT',

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP
            , "active_source_count" INTEGER NOT NULL DEFAULT 1, "last_verified_at" TEXT, "disappeared_at" TEXT);

CREATE TABLE collection_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    hours_lookback INTEGER NOT NULL,
    jobs_found INTEGER DEFAULT 0,
    jobs_added INTEGER DEFAULT 0,
    jobs_updated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'RUNNING',
    error_message TEXT
);

CREATE TABLE combined_sponsor_universe (
                parent_key TEXT PRIMARY KEY,

                display_name TEXT NOT NULL,

                dol_present INTEGER NOT NULL DEFAULT 0,
                uscis_present INTEGER NOT NULL DEFAULT 0,

                dol_recent_filings INTEGER NOT NULL DEFAULT 0,
                dol_total_filings INTEGER NOT NULL DEFAULT 0,
                dol_strength TEXT NOT NULL DEFAULT 'UNKNOWN',

                uscis_active_years INTEGER NOT NULL DEFAULT 0,

                uscis_2025_approvals INTEGER NOT NULL DEFAULT 0,
                uscis_2026_approvals INTEGER NOT NULL DEFAULT 0,

                uscis_total_approvals INTEGER NOT NULL DEFAULT 0,
                uscis_total_denials INTEGER NOT NULL DEFAULT 0,

                uscis_strength TEXT NOT NULL DEFAULT 'UNKNOWN',

                dol_score_component REAL NOT NULL DEFAULT 0,
                uscis_volume_component REAL NOT NULL DEFAULT 0,
                consistency_component REAL NOT NULL DEFAULT 0,
                approval_component REAL NOT NULL DEFAULT 0,
                current_activity_component REAL NOT NULL DEFAULT 0,

                combined_sponsor_score REAL NOT NULL DEFAULT 0,
                combined_priority_band TEXT NOT NULL DEFAULT 'LOW',

                already_in_registry INTEGER NOT NULL DEFAULT 0,
                matched_employer_id INTEGER,

                source_resolution_status TEXT NOT NULL DEFAULT 'UNRESOLVED',

                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            , employer_relevance_band TEXT, employer_relevance_score INTEGER NOT NULL DEFAULT 0, employer_relevance_reason TEXT, source_discovery_score REAL NOT NULL DEFAULT 0);

CREATE TABLE companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    website TEXT,
    careers_url TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE discovered_job_feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                employer_identity_id INTEGER,
                employer_name TEXT NOT NULL,

                seed_url TEXT,
                feed_url TEXT NOT NULL,

                feed_type TEXT NOT NULL,

                confidence REAL NOT NULL
                    DEFAULT 0,

                discovery_method TEXT,

                enabled INTEGER NOT NULL
                    DEFAULT 1,

                verification_status TEXT NOT NULL
                    DEFAULT 'UNVERIFIED',

                last_run_at TEXT,
                last_job_count INTEGER NOT NULL
                    DEFAULT 0,

                last_error TEXT,

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(
                    employer_name,
                    feed_url
                )
            );

CREATE TABLE employer_identities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            identity_key TEXT NOT NULL UNIQUE,

            canonical_name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,

            sponsor_parent_key TEXT,
            registry_employer_id INTEGER,

            primary_domain TEXT,

            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            updated_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE employer_identity_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                parent_key TEXT NOT NULL,

                alias_name TEXT NOT NULL,
                normalized_alias TEXT NOT NULL,

                alias_type TEXT NOT NULL
                    DEFAULT 'SPONSOR_NAME',

                domain TEXT,

                confidence REAL NOT NULL DEFAULT 1.0,

                source TEXT,

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(parent_key, normalized_alias)
            );

CREATE TABLE employer_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employer_id INTEGER NOT NULL,
    ats TEXT NOT NULL,
    token TEXT,
    careers_url TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_checked_at TEXT,
    last_success_at TEXT,
    active_jobs INTEGER DEFAULT 0,
    source_verified INTEGER DEFAULT 0,
    notes TEXT,
    FOREIGN KEY(employer_id) REFERENCES employers(id) ON DELETE CASCADE
);

CREATE TABLE employers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'DIRECT_EMPLOYER',
    website TEXT,
    careers_url TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ingestion_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                provider TEXT NOT NULL,
                provider_source_id TEXT,

                transport_type TEXT,
                batch_name TEXT,

                status TEXT NOT NULL DEFAULT 'RUNNING',

                started_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                finished_at TEXT,

                raw_found INTEGER NOT NULL DEFAULT 0,
                observations_inserted INTEGER NOT NULL DEFAULT 0,
                observations_updated INTEGER NOT NULL DEFAULT 0,
                observations_failed INTEGER NOT NULL DEFAULT 0,

                employers_resolved INTEGER NOT NULL DEFAULT 0,
                employers_unresolved INTEGER NOT NULL DEFAULT 0,

                canonical_jobs_created INTEGER NOT NULL DEFAULT 0,
                canonical_jobs_updated INTEGER NOT NULL DEFAULT 0,

                error TEXT,
                metadata_json TEXT
            , "observations_deactivated" INTEGER NOT NULL DEFAULT 0, "canonical_jobs_deactivated" INTEGER NOT NULL DEFAULT 0);

CREATE TABLE job_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                observation_key TEXT NOT NULL UNIQUE,

                provider TEXT NOT NULL,
                provider_job_id TEXT,

                source_type TEXT NOT NULL,
                transport_type TEXT,

                source_url TEXT NOT NULL,
                apply_url TEXT,

                company_name_raw TEXT NOT NULL,
                company_domain TEXT,

                title_raw TEXT NOT NULL,
                location_raw TEXT,
                description_raw TEXT,

                posted_at TEXT,

                raw_payload_json TEXT,
                payload_hash TEXT,

                sponsor_parent_key TEXT,
                sponsor_match_confidence REAL DEFAULT 0,

                canonical_job_id INTEGER,

                source_confidence_score REAL DEFAULT 0,

                first_seen_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                last_seen_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                is_active INTEGER NOT NULL DEFAULT 1
            , "ingestion_run_id" INTEGER, "provider_source_id" TEXT, "employer_identity_id" INTEGER, "employer_resolution_method" TEXT, "employer_resolution_confidence" REAL DEFAULT 0, "normalization_status" TEXT DEFAULT 'PENDING', "canonicalization_status" TEXT DEFAULT 'PENDING', "last_error" TEXT, "disappeared_at" TEXT, "last_verified_at" TEXT);

CREATE TABLE job_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    skill TEXT NOT NULL,
    matched_to_profile INTEGER DEFAULT 0,
    FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE TABLE job_transports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                transport_key TEXT NOT NULL UNIQUE,

                employer_parent_key TEXT,

                provider TEXT NOT NULL,
                transport_type TEXT NOT NULL,

                base_url TEXT,
                token TEXT,

                confidence REAL DEFAULT 0,

                enabled INTEGER NOT NULL DEFAULT 1,

                last_success_at TEXT,
                last_failure_at TEXT,
                last_error TEXT,

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP
            );

CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    apply_url TEXT,
    company_id INTEGER,
    company_name_raw TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    location_raw TEXT,
    country TEXT,
    posted_at TEXT,
    first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,

    min_experience_years REAL,
    max_experience_years REAL,
    experience_text TEXT,
    experience_match INTEGER,

    work_arrangement TEXT CHECK (
        work_arrangement IN ('REMOTE','HYBRID','ONSITE','UNKNOWN')
    ) DEFAULT 'UNKNOWN',

    employment_type TEXT CHECK (
        employment_type IN (
            'FULL_TIME',
            'CONTRACT_W2',
            'CONTRACT_C2C',
            'CONTRACT_UNKNOWN',
            'TEMPORARY',
            'INTERNSHIP',
            'UNKNOWN'
        )
    ) DEFAULT 'UNKNOWN',

    visa_language_status TEXT CHECK (
        visa_language_status IN (
            'SPONSORSHIP_AVAILABLE',
            'OPT_F1_MENTIONED',
            'NO_SPONSORSHIP',
            'RESTRICTED',
            'NOT_MENTIONED',
            'UNKNOWN'
        )
    ) DEFAULT 'UNKNOWN',

    visa_evidence_text TEXT,
    h1b_history_strength TEXT CHECK (
        h1b_history_strength IN ('STRONG','MEDIUM','LOW','UNKNOWN')
    ) DEFAULT 'UNKNOWN',

    sponsorship_score REAL DEFAULT 0,
    overall_score REAL DEFAULT 0,

    decision TEXT CHECK (
        decision IN ('APPLY','OK_TO_APPLY','NEEDS_REVIEW','SKIP')
    ) DEFAULT 'NEEDS_REVIEW',

    decision_reason TEXT,

    application_status TEXT CHECK (
        application_status IN (
            'NEW','SAVED','APPLIED','INTERVIEW','REJECTED','SKIPPED'
        )
    ) DEFAULT 'NEW',

    date_applied TEXT,
    notes TEXT, source_type TEXT DEFAULT 'DIRECT_EMPLOYER', ats TEXT, experience_band TEXT, visa_detail_status TEXT, agency_name TEXT, end_client TEXT, employment_detail_type TEXT, source_published_at TEXT, source_updated_at TEXT, effective_posted_at TEXT, freshness_confidence TEXT, freshness_source TEXT, source_confidence_score REAL DEFAULT 0, source_confidence_label TEXT, dedupe_key TEXT, is_active INTEGER DEFAULT 1, last_verified_at TEXT, disappeared_at TEXT, is_eligible INTEGER DEFAULT 1, eligibility_reason TEXT, location_eligibility TEXT, experience_eligibility TEXT,

    FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE SET NULL
);

CREATE TABLE source_discovery_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                batch_name TEXT NOT NULL,

                parent_key TEXT NOT NULL,
                display_name TEXT NOT NULL,

                combined_sponsor_score REAL NOT NULL,
                employer_relevance_band TEXT,
                source_discovery_score REAL NOT NULL,

                dol_recent_filings INTEGER NOT NULL DEFAULT 0,
                uscis_2025_approvals INTEGER NOT NULL DEFAULT 0,
                uscis_2026_approvals INTEGER NOT NULL DEFAULT 0,

                resolution_status TEXT NOT NULL DEFAULT 'PENDING',

                discovered_careers_url TEXT,
                discovered_ats TEXT,
                discovered_token TEXT,

                verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED',

                notes TEXT,

                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, careers_discovery_status TEXT, careers_candidate_url TEXT, careers_discovery_score REAL,

                UNIQUE(batch_name, parent_key)
            );

CREATE TABLE sponsor_employer_universe (
    normalized_name TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,

    latest_year INTEGER,
    total_filings INTEGER NOT NULL DEFAULT 0,
    recent_filings INTEGER NOT NULL DEFAULT 0,

    approved_count INTEGER NOT NULL DEFAULT 0,
    denied_count INTEGER NOT NULL DEFAULT 0,

    sponsor_strength TEXT NOT NULL DEFAULT 'UNKNOWN',

    dol_present INTEGER NOT NULL DEFAULT 0,
    uscis_present INTEGER NOT NULL DEFAULT 0,

    matched_employer_id INTEGER,
    already_in_registry INTEGER NOT NULL DEFAULT 0,

    careers_url TEXT,
    careers_url_status TEXT NOT NULL DEFAULT 'UNKNOWN',

    ats_candidate TEXT,
    source_resolution_status TEXT NOT NULL DEFAULT 'UNRESOLVED',

    priority_score REAL NOT NULL DEFAULT 0,
    priority_band TEXT NOT NULL DEFAULT 'LOW',

    first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_ranked_at TEXT,

    notes TEXT
);

CREATE TABLE sponsor_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    source_year INTEGER,
    filings_count INTEGER,
    approved_count INTEGER,
    denied_count INTEGER,
    sponsor_strength TEXT CHECK (
        sponsor_strength IN ('STRONG','MEDIUM','LOW','UNKNOWN')
    ) DEFAULT 'UNKNOWN',
    evidence_url TEXT,
    last_verified_at TEXT,
    FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
);

CREATE TABLE sponsor_parent_groups (
            parent_key TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,

            total_filings INTEGER NOT NULL DEFAULT 0,
            recent_filings INTEGER NOT NULL DEFAULT 0,

            legal_entity_count INTEGER NOT NULL DEFAULT 0,

            strongest_sponsor_strength TEXT NOT NULL DEFAULT 'UNKNOWN',
            highest_priority_score REAL NOT NULL DEFAULT 0,
            priority_band TEXT NOT NULL DEFAULT 'LOW',

            already_in_registry INTEGER NOT NULL DEFAULT 0,
            matched_employer_id INTEGER,

            source_resolution_status TEXT NOT NULL DEFAULT 'UNRESOLVED',

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE sponsor_parent_members (
            parent_key TEXT NOT NULL,
            normalized_name TEXT NOT NULL,

            PRIMARY KEY (
                parent_key,
                normalized_name
            )
        );

CREATE TABLE sponsor_rollup (
                normalized_name TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'DOL_OFLC_LCA',
                total_filings INTEGER NOT NULL DEFAULT 0,
                approved_count INTEGER NOT NULL DEFAULT 0,
                denied_count INTEGER NOT NULL DEFAULT 0,
                recent_filings INTEGER NOT NULL DEFAULT 0,
                latest_year INTEGER,
                sponsor_strength TEXT NOT NULL DEFAULT 'UNKNOWN',
                last_verified_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

CREATE TABLE structured_web_seeds (
                id INTEGER PRIMARY KEY
                    AUTOINCREMENT,

                employer_identity_id INTEGER,

                employer_name TEXT
                    NOT NULL,

                seed_url TEXT
                    NOT NULL,

                seed_source TEXT
                    NOT NULL,

                confidence REAL
                    NOT NULL DEFAULT 0,

                enabled INTEGER
                    NOT NULL DEFAULT 1,

                last_run_at TEXT,
                last_job_count INTEGER
                    NOT NULL DEFAULT 0,

                last_error TEXT,

                created_at TEXT
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(
                    employer_name,
                    seed_url
                )
            );

CREATE TABLE transport_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                employer_identity_id INTEGER,
                employer_name TEXT NOT NULL,

                seed_url TEXT NOT NULL,

                transport_type TEXT NOT NULL,
                transport_url TEXT,

                confidence REAL NOT NULL DEFAULT 0,

                discovery_method TEXT,
                evidence TEXT,

                verification_status TEXT NOT NULL
                    DEFAULT 'UNVERIFIED',

                enabled INTEGER NOT NULL DEFAULT 1,

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(
                    employer_name,
                    transport_type,
                    transport_url
                )
            );

CREATE TABLE uscis_h1b_employer_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                normalized_name TEXT NOT NULL,
                display_name TEXT NOT NULL,
                fiscal_year INTEGER NOT NULL,

                employer_city TEXT,
                employer_state TEXT,
                employer_zip TEXT,

                tax_id TEXT,
                naics_code TEXT,

                new_employment_approvals INTEGER NOT NULL DEFAULT 0,
                new_employment_denials INTEGER NOT NULL DEFAULT 0,

                continuation_approvals INTEGER NOT NULL DEFAULT 0,
                continuation_denials INTEGER NOT NULL DEFAULT 0,

                same_employer_approvals INTEGER NOT NULL DEFAULT 0,
                same_employer_denials INTEGER NOT NULL DEFAULT 0,

                new_concurrent_approvals INTEGER NOT NULL DEFAULT 0,
                new_concurrent_denials INTEGER NOT NULL DEFAULT 0,

                change_employer_approvals INTEGER NOT NULL DEFAULT 0,
                change_employer_denials INTEGER NOT NULL DEFAULT 0,

                amended_approvals INTEGER NOT NULL DEFAULT 0,
                amended_denials INTEGER NOT NULL DEFAULT 0,

                initial_approvals INTEGER NOT NULL DEFAULT 0,
                initial_denials INTEGER NOT NULL DEFAULT 0,

                continuing_approvals INTEGER NOT NULL DEFAULT 0,
                continuing_denials INTEGER NOT NULL DEFAULT 0,

                total_approvals INTEGER NOT NULL DEFAULT 0,
                total_denials INTEGER NOT NULL DEFAULT 0,

                source TEXT NOT NULL
                    DEFAULT 'USCIS_H1B_EMPLOYER_DATA_HUB',

                source_file TEXT,
                source_row_number INTEGER,

                row_fingerprint TEXT NOT NULL UNIQUE,

                imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

CREATE TABLE uscis_h1b_parent_rollup (
                parent_key TEXT PRIMARY KEY,

                display_name TEXT NOT NULL,

                matched_uscis_entities
                    INTEGER NOT NULL DEFAULT 0,

                dol_parent_present
                    INTEGER NOT NULL DEFAULT 0,

                active_years INTEGER NOT NULL DEFAULT 0,

                approvals_2022 INTEGER NOT NULL DEFAULT 0,
                approvals_2023 INTEGER NOT NULL DEFAULT 0,
                approvals_2024 INTEGER NOT NULL DEFAULT 0,
                approvals_2025 INTEGER NOT NULL DEFAULT 0,
                approvals_2026 INTEGER NOT NULL DEFAULT 0,

                total_approvals INTEGER NOT NULL DEFAULT 0,
                total_denials INTEGER NOT NULL DEFAULT 0,

                complete_year_approvals
                    INTEGER NOT NULL DEFAULT 0,

                current_year_approvals
                    INTEGER NOT NULL DEFAULT 0,

                approval_rate REAL,

                uscis_strength TEXT NOT NULL
                    DEFAULT 'UNKNOWN',

                last_verified_at TEXT
                    DEFAULT CURRENT_TIMESTAMP
            );

CREATE TABLE uscis_h1b_rollup (
                normalized_name TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,

                first_year INTEGER,
                latest_year INTEGER,
                active_years INTEGER NOT NULL DEFAULT 0,

                approvals_2022 INTEGER NOT NULL DEFAULT 0,
                approvals_2023 INTEGER NOT NULL DEFAULT 0,
                approvals_2024 INTEGER NOT NULL DEFAULT 0,
                approvals_2025 INTEGER NOT NULL DEFAULT 0,
                approvals_2026 INTEGER NOT NULL DEFAULT 0,

                denials_2022 INTEGER NOT NULL DEFAULT 0,
                denials_2023 INTEGER NOT NULL DEFAULT 0,
                denials_2024 INTEGER NOT NULL DEFAULT 0,
                denials_2025 INTEGER NOT NULL DEFAULT 0,
                denials_2026 INTEGER NOT NULL DEFAULT 0,

                new_employment_approvals INTEGER NOT NULL DEFAULT 0,
                new_employment_denials INTEGER NOT NULL DEFAULT 0,

                continuation_approvals INTEGER NOT NULL DEFAULT 0,
                continuation_denials INTEGER NOT NULL DEFAULT 0,

                total_approvals INTEGER NOT NULL DEFAULT 0,
                total_denials INTEGER NOT NULL DEFAULT 0,

                complete_year_approvals INTEGER NOT NULL DEFAULT 0,
                current_year_approvals INTEGER NOT NULL DEFAULT 0,

                approval_rate REAL,

                uscis_strength TEXT NOT NULL DEFAULT 'UNKNOWN',

                last_verified_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

CREATE INDEX idx_canonical_active_sources
            ON canonical_jobs(
                is_active,
                active_source_count
            );

CREATE INDEX idx_canonical_job_sources_job
            ON canonical_job_sources(
                canonical_job_id
            );

CREATE INDEX idx_canonical_job_sources_provider
            ON canonical_job_sources(
                provider
            );

CREATE INDEX idx_canonical_jobs_active
            ON canonical_jobs(
                is_active
            );

CREATE INDEX idx_canonical_jobs_employer
            ON canonical_jobs(
                employer_identity_id
            );

CREATE INDEX idx_canonical_jobs_posted
            ON canonical_jobs(
                posted_at
            );

CREATE INDEX idx_combined_sponsor_score
            ON combined_sponsor_universe(
                combined_sponsor_score DESC
            );

CREATE INDEX idx_discovered_job_feeds_identity
            ON discovered_job_feeds(
                employer_identity_id
            );

CREATE INDEX idx_discovered_job_feeds_type
            ON discovered_job_feeds(
                feed_type
            );

CREATE INDEX idx_employer_alias_normalized
            ON employer_identity_aliases(normalized_alias);

CREATE INDEX idx_employer_identities_normalized
        ON employer_identities(normalized_name);

CREATE INDEX idx_employer_identities_registry
        ON employer_identities(registry_employer_id);

CREATE INDEX idx_employer_identities_sponsor
        ON employer_identities(sponsor_parent_key);

CREATE INDEX idx_employer_identity_alias_normalized
        ON employer_identity_aliases(normalized_alias);

CREATE INDEX idx_employer_sources_ats ON employer_sources(ats);

CREATE INDEX idx_employer_sources_enabled ON employer_sources(enabled);

CREATE INDEX idx_ingestion_runs_provider
            ON ingestion_runs(provider);

CREATE INDEX idx_ingestion_runs_started
            ON ingestion_runs(started_at);

CREATE INDEX idx_ingestion_runs_status
            ON ingestion_runs(status);

CREATE INDEX idx_job_enrichment_eligible
            ON canonical_job_enrichment(
                is_eligible
            );

CREATE INDEX idx_job_enrichment_score
            ON canonical_job_enrichment(
                overall_score DESC
            );

CREATE INDEX idx_job_enrichment_software
            ON canonical_job_enrichment(
                is_software_role
            );

CREATE INDEX idx_job_enrichment_sponsor
            ON canonical_job_enrichment(
                sponsor_parent_key
            );

CREATE INDEX idx_job_observations_canonical
            ON job_observations(canonical_job_id);

CREATE INDEX idx_job_observations_company
            ON job_observations(company_name_raw);

CREATE INDEX idx_job_observations_identity
            ON job_observations(employer_identity_id);

CREATE INDEX idx_job_observations_provider
            ON job_observations(provider);

CREATE INDEX idx_job_observations_run
            ON job_observations(ingestion_run_id);

CREATE INDEX idx_job_observations_sponsor
            ON job_observations(sponsor_parent_key);

CREATE INDEX idx_job_observations_status
            ON job_observations(
                normalization_status,
                canonicalization_status
            );

CREATE INDEX idx_job_transports_parent
            ON job_transports(employer_parent_key);

CREATE INDEX idx_jobs_agency_name ON jobs(agency_name);

CREATE INDEX idx_jobs_application_status
ON jobs(application_status);

CREATE INDEX idx_jobs_ats ON jobs(ats);

CREATE INDEX idx_jobs_decision
ON jobs(decision);

CREATE INDEX idx_jobs_dedupe_key ON jobs(dedupe_key);

CREATE INDEX idx_jobs_employment_detail_type ON jobs(employment_detail_type);

CREATE INDEX idx_jobs_employment_type
ON jobs(employment_type);

CREATE INDEX idx_jobs_experience_band ON jobs(experience_band);

CREATE INDEX idx_jobs_posted_at
ON jobs(posted_at);

CREATE INDEX idx_jobs_source_type ON jobs(source_type);

CREATE INDEX idx_jobs_visa_detail_status ON jobs(visa_detail_status);

CREATE INDEX idx_jobs_work_arrangement
ON jobs(work_arrangement);

CREATE INDEX idx_observations_provider_source_active
            ON job_observations(
                provider,
                provider_source_id,
                is_active
            );

CREATE INDEX idx_sponsor_parent_priority
            ON sponsor_parent_groups(
                highest_priority_score DESC
            );

CREATE INDEX idx_sponsor_universe_priority
    ON sponsor_employer_universe(priority_score DESC);

CREATE INDEX idx_sponsor_universe_registry
    ON sponsor_employer_universe(already_in_registry);

CREATE INDEX idx_sponsor_universe_resolution
    ON sponsor_employer_universe(source_resolution_status);

CREATE INDEX idx_sponsor_universe_strength
    ON sponsor_employer_universe(sponsor_strength);

CREATE INDEX idx_transport_candidates_identity
            ON transport_candidates(
                employer_identity_id
            );

CREATE INDEX idx_transport_candidates_type
            ON transport_candidates(
                transport_type
            );

CREATE INDEX idx_uscis_history_name
            ON uscis_h1b_employer_history(normalized_name);

CREATE INDEX idx_uscis_history_year
            ON uscis_h1b_employer_history(fiscal_year);

CREATE INDEX idx_uscis_parent_complete
            ON uscis_h1b_parent_rollup(
                complete_year_approvals DESC
            );

CREATE INDEX idx_uscis_parent_strength
            ON uscis_h1b_parent_rollup(
                uscis_strength
            );

CREATE INDEX idx_uscis_rollup_complete_year
            ON uscis_h1b_rollup(complete_year_approvals DESC);

CREATE INDEX idx_uscis_rollup_total_approvals
            ON uscis_h1b_rollup(total_approvals DESC);

PRAGMA foreign_keys = ON;
