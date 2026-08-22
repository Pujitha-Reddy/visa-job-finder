from __future__ import annotations

from app.database import (
    get_connection,
)

from app.ingestion.canonical_normalize import (
    canonical_key_for_observation,
)


def choose_value(
    existing_value,
    new_value,
    existing_confidence,
    new_confidence,
):
    if not new_value:
        return existing_value

    if not existing_value:
        return new_value

    if new_confidence > existing_confidence:
        return new_value

    return existing_value


def canonicalize_observation(
    observation,
):
    (
        canonical_key,
        match_method,
        match_confidence,
    ) = canonical_key_for_observation(
        observation
    )

    source_confidence = float(
        observation[
            "source_confidence_score"
        ]
        or 0
    )

    with get_connection() as conn:

        existing = conn.execute(
            """
            SELECT *
            FROM canonical_jobs
            WHERE canonical_key=?
            """,
            (canonical_key,),
        ).fetchone()

        if existing:
            canonical_id = existing[
                "id"
            ]

            best_confidence = float(
                existing[
                    "best_source_confidence"
                ]
                or 0
            )

            title = choose_value(
                existing[
                    "canonical_title"
                ],
                observation[
                    "title_raw"
                ],
                best_confidence,
                source_confidence,
            )

            location = choose_value(
                existing[
                    "canonical_location"
                ],
                observation[
                    "location_raw"
                ],
                best_confidence,
                source_confidence,
            )

            description = choose_value(
                existing[
                    "description"
                ],
                observation[
                    "description_raw"
                ],
                best_confidence,
                source_confidence,
            )

            source_url = choose_value(
                existing[
                    "preferred_source_url"
                ],
                observation[
                    "source_url"
                ],
                best_confidence,
                source_confidence,
            )

            apply_url = choose_value(
                existing[
                    "preferred_apply_url"
                ],
                observation[
                    "apply_url"
                ],
                best_confidence,
                source_confidence,
            )

            posted_at = (
                existing["posted_at"]
            )

            # Prefer earliest credible posting date.
            incoming_posted = observation[
                "posted_at"
            ]

            if incoming_posted:
                if (
                    not posted_at
                    or incoming_posted
                    < posted_at
                ):
                    posted_at = (
                        incoming_posted
                    )

            conn.execute(
                """
                UPDATE canonical_jobs
                SET
                    canonical_title=?,
                    canonical_location=?,
                    description=?,

                    preferred_source_url=?,
                    preferred_apply_url=?,

                    posted_at=?,

                    last_seen_at=
                        CURRENT_TIMESTAMP,

                    is_active=1,

                    best_source_confidence=
                        MAX(
                            best_source_confidence,
                            ?
                        ),

                    canonicalization_confidence=
                        MAX(
                            canonicalization_confidence,
                            ?
                        ),

                    updated_at=
                        CURRENT_TIMESTAMP

                WHERE id=?
                """,
                (
                    title,
                    location,
                    description,

                    source_url,
                    apply_url,

                    posted_at,

                    source_confidence,
                    match_confidence,

                    canonical_id,
                ),
            )

            action = "UPDATED"

        else:
            cur = conn.execute(
                """
                INSERT INTO canonical_jobs (
                    canonical_key,

                    employer_identity_id,

                    canonical_title,
                    canonical_location,

                    description,

                    preferred_source_url,
                    preferred_apply_url,

                    external_id,

                    posted_at,

                    best_source_confidence,
                    canonicalization_confidence
                )
                VALUES (
                    ?, ?,
                    ?, ?,
                    ?,
                    ?, ?,
                    ?,
                    ?,
                    ?, ?
                )
                """,
                (
                    canonical_key,

                    observation[
                        "employer_identity_id"
                    ],

                    observation[
                        "title_raw"
                    ],

                    observation[
                        "location_raw"
                    ],

                    observation[
                        "description_raw"
                    ],

                    observation[
                        "source_url"
                    ],

                    observation[
                        "apply_url"
                    ],

                    observation[
                        "provider_job_id"
                    ],

                    observation[
                        "posted_at"
                    ],

                    source_confidence,
                    match_confidence,
                ),
            )

            canonical_id = (
                cur.lastrowid
            )

            action = "INSERTED"

        # ==================================================
        # Observation edge
        # ==================================================

        conn.execute(
            """
            INSERT INTO canonical_job_sources (
                canonical_job_id,
                observation_id,

                provider,

                source_confidence,
                match_method,
                match_confidence,

                is_active
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, 1
            )

            ON CONFLICT(
                observation_id
            )
            DO UPDATE SET
                canonical_job_id=
                    excluded.canonical_job_id,

                source_confidence=
                    excluded.source_confidence,

                match_method=
                    excluded.match_method,

                match_confidence=
                    excluded.match_confidence,

                last_seen_at=
                    CURRENT_TIMESTAMP,

                is_active=1
            """,
            (
                canonical_id,
                observation["id"],

                observation[
                    "provider"
                ],

                source_confidence,
                match_method,
                match_confidence,
            ),
        )

        # ==================================================
        # Recompute source count
        # ==================================================

        source_count = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM canonical_job_sources
            WHERE canonical_job_id=?
              AND is_active=1
            """,
            (canonical_id,),
        ).fetchone()["n"]

        conn.execute(
            """
            UPDATE canonical_jobs
            SET source_count=?
            WHERE id=?
            """,
            (
                source_count,
                canonical_id,
            ),
        )

        # Observation now points to canonical job.
        conn.execute(
            """
            UPDATE job_observations
            SET
                canonical_job_id=?,
                canonicalization_status=
                    'CANONICALIZED',
                last_error=NULL
            WHERE id=?
            """,
            (
                canonical_id,
                observation["id"],
            ),
        )

        conn.commit()

    return {
        "canonical_job_id": (
            canonical_id
        ),
        "action": action,
        "match_method": (
            match_method
        ),
        "match_confidence": (
            match_confidence
        ),
    }
