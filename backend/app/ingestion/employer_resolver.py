from __future__ import annotations

import re
from urllib.parse import urlparse

from app.database import get_connection


LEGAL_SUFFIXES = re.compile(
    r"""
    \b(
        incorporated|inc|
        corporation|corp|
        limited|ltd|
        llc|
        company|co|
        plc|
        lp
    )\b\.?
    """,
    re.IGNORECASE | re.VERBOSE,
)


def normalize_name(value):
    value = (value or "").lower().strip()

    if not value:
        return ""

    value = value.replace("&", " and ")
    value = LEGAL_SUFFIXES.sub(" ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def domain_from_url(value):
    if not value:
        return None

    try:
        host = urlparse(value).hostname
    except Exception:
        return None

    if not host:
        return None

    host = host.lower()

    if host.startswith("www."):
        host = host[4:]

    return host


def resolve_by_registry_source(
    conn,
    provider_source_id,
):
    if not provider_source_id:
        return None

    try:
        source_id = int(
            provider_source_id
        )
    except Exception:
        return None

    row = conn.execute(
        """
        SELECT
            e.id AS identity_id,
            e.identity_key,
            e.canonical_name
        FROM employer_sources s
        JOIN employer_identities e
          ON e.registry_employer_id =
             s.employer_id
        WHERE s.id=?
        LIMIT 1
        """,
        (source_id,),
    ).fetchone()

    if not row:
        return None

    return {
        "employer_identity_id": row[
            "identity_id"
        ],
        "method": "REGISTRY_SOURCE_ID",
        "confidence": 1.0,
    }


def resolve_by_domain(
    conn,
    source_url,
    company_domain,
):
    domain = (
        company_domain
        or domain_from_url(source_url)
    )

    if not domain:
        return None

    rows = conn.execute(
        """
        SELECT
            id,
            primary_domain
        FROM employer_identities
        WHERE primary_domain IS NOT NULL
        """
    ).fetchall()

    exact = []

    for row in rows:
        candidate = (
            row["primary_domain"]
            or ""
        ).lower()

        if not candidate:
            continue

        if domain == candidate:
            exact.append(
                row["id"]
            )

    if len(exact) == 1:
        return {
            "employer_identity_id": (
                exact[0]
            ),
            "method": "EXACT_DOMAIN",
            "confidence": 0.99,
        }

    return None


def resolve_by_alias(
    conn,
    company_name,
):
    normalized = normalize_name(
        company_name
    )

    if not normalized:
        return None

    rows = conn.execute(
        """
        SELECT DISTINCT
            e.id AS identity_id
        FROM employer_identity_aliases a
        JOIN employer_identities e
          ON e.identity_key =
             a.parent_key
        WHERE a.normalized_alias=?
        """,
        (normalized,),
    ).fetchall()

    if len(rows) == 1:
        return {
            "employer_identity_id": rows[
                0
            ]["identity_id"],
            "method": "EXACT_ALIAS",
            "confidence": 0.98,
        }

    return None


def resolve_by_canonical_name(
    conn,
    company_name,
):
    normalized = normalize_name(
        company_name
    )

    if not normalized:
        return None

    rows = conn.execute(
        """
        SELECT id
        FROM employer_identities
        WHERE normalized_name=?
        """,
        (normalized,),
    ).fetchall()

    if len(rows) == 1:
        return {
            "employer_identity_id": (
                rows[0]["id"]
            ),
            "method": (
                "EXACT_CANONICAL_NAME"
            ),
            "confidence": 0.97,
        }

    return None


def resolve_by_containment(
    conn,
    company_name,
):
    normalized = normalize_name(
        company_name
    )

    # Avoid dangerous short-name matching.
    if len(normalized) < 8:
        return None

    rows = conn.execute(
        """
        SELECT DISTINCT
            e.id AS identity_id,
            a.normalized_alias
        FROM employer_identity_aliases a
        JOIN employer_identities e
          ON e.identity_key =
             a.parent_key
        WHERE length(
            a.normalized_alias
        ) >= 8
        """
    ).fetchall()

    matches = {}

    for row in rows:
        alias = row[
            "normalized_alias"
        ]

        if not alias:
            continue

        if (
            normalized == alias
            or normalized in alias
            or alias in normalized
        ):
            identity_id = row[
                "identity_id"
            ]

            score = (
                min(
                    len(normalized),
                    len(alias),
                )
                /
                max(
                    len(normalized),
                    len(alias),
                )
            )

            if score < 0.80:
                continue

            previous = matches.get(
                identity_id,
                0,
            )

            matches[
                identity_id
            ] = max(
                previous,
                score,
            )

    if not matches:
        return None

    ranked = sorted(
        matches.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    )

    best_id, best_score = ranked[0]

    # Ambiguous near-tie:
    # do not guess.
    if len(ranked) > 1:
        second_score = ranked[
            1
        ][1]

        if abs(
            best_score
            - second_score
        ) < 0.03:
            return None

    return {
        "employer_identity_id": (
            best_id
        ),
        "method": (
            "NORMALIZED_CONTAINMENT"
        ),
        "confidence": round(
            0.80
            + (
                min(best_score, 1.0)
                * 0.10
            ),
            4,
        ),
    }


def resolve_observation(
    observation,
):
    with get_connection() as conn:

        resolvers = (
            lambda: resolve_by_registry_source(
                conn,
                observation[
                    "provider_source_id"
                ],
            ),

            lambda: resolve_by_domain(
                conn,
                observation[
                    "source_url"
                ],
                observation[
                    "company_domain"
                ],
            ),

            lambda: resolve_by_alias(
                conn,
                observation[
                    "company_name_raw"
                ],
            ),

            lambda: resolve_by_canonical_name(
                conn,
                observation[
                    "company_name_raw"
                ],
            ),

            lambda: resolve_by_containment(
                conn,
                observation[
                    "company_name_raw"
                ],
            ),
        )

        for resolver in resolvers:
            result = resolver()

            if result:
                return result

    return {
        "employer_identity_id": None,
        "method": "UNRESOLVED",
        "confidence": 0.0,
    }
