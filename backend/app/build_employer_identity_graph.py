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
        parsed = urlparse(value)
        host = parsed.hostname
    except Exception:
        return None

    if not host:
        return None

    host = host.lower()

    if host.startswith("www."):
        host = host[4:]

    return host


def table_exists(conn, table):
    return (
        conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table'
              AND name=?
            """,
            (table,),
        ).fetchone()
        is not None
    )


def columns(conn, table):
    if not table_exists(conn, table):
        return set()

    return {
        row["name"]
        for row in conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    }


def create_schema(conn):
    # ======================================================
    # Canonical employer identity nodes
    #
    # identity_key is sponsor parent_key where possible.
    #
    # For registry-only companies:
    # REGISTRY:<employer_id>
    # ======================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS employer_identities (
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
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_employer_identities_normalized
        ON employer_identities(normalized_name)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_employer_identities_registry
        ON employer_identities(registry_employer_id)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_employer_identities_sponsor
        ON employer_identities(sponsor_parent_key)
    """)

    # ======================================================
    # V100 alias table
    #
    # IMPORTANT:
    # Keep the schema already created by V100.
    # ======================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS employer_identity_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            parent_key TEXT NOT NULL,

            alias_name TEXT NOT NULL,
            normalized_alias TEXT NOT NULL,

            alias_type TEXT NOT NULL
                DEFAULT 'SPONSOR_NAME',

            domain TEXT,

            confidence REAL NOT NULL
                DEFAULT 1.0,

            source TEXT,

            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(
                parent_key,
                normalized_alias
            )
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_employer_alias_normalized
        ON employer_identity_aliases(
            normalized_alias
        )
    """)


def upsert_identity(
    conn,
    *,
    identity_key,
    canonical_name,
    sponsor_parent_key=None,
    registry_employer_id=None,
    primary_domain=None,
):
    normalized = normalize_name(
        canonical_name
    )

    if not identity_key or not normalized:
        return None

    existing = conn.execute(
        """
        SELECT id
        FROM employer_identities
        WHERE identity_key=?
        """,
        (identity_key,),
    ).fetchone()

    if existing:
        conn.execute(
            """
            UPDATE employer_identities
            SET
                canonical_name=?,
                normalized_name=?,

                sponsor_parent_key=
                    COALESCE(
                        sponsor_parent_key,
                        ?
                    ),

                registry_employer_id=
                    COALESCE(
                        registry_employer_id,
                        ?
                    ),

                primary_domain=
                    COALESCE(
                        primary_domain,
                        ?
                    ),

                updated_at=CURRENT_TIMESTAMP

            WHERE id=?
            """,
            (
                canonical_name,
                normalized,
                sponsor_parent_key,
                registry_employer_id,
                primary_domain,
                existing["id"],
            ),
        )

        return existing["id"]

    cur = conn.execute(
        """
        INSERT INTO employer_identities (
            identity_key,
            canonical_name,
            normalized_name,
            sponsor_parent_key,
            registry_employer_id,
            primary_domain
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            identity_key,
            canonical_name,
            normalized,
            sponsor_parent_key,
            registry_employer_id,
            primary_domain,
        ),
    )

    return cur.lastrowid


def add_alias(
    conn,
    *,
    parent_key,
    alias_name,
    alias_type,
    domain=None,
    confidence=1.0,
    source=None,
):
    normalized = normalize_name(
        alias_name
    )

    if not parent_key or not normalized:
        return False

    conn.execute(
        """
        INSERT INTO employer_identity_aliases (
            parent_key,
            alias_name,
            normalized_alias,
            alias_type,
            domain,
            confidence,
            source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(
            parent_key,
            normalized_alias
        )
        DO UPDATE SET
            alias_name=excluded.alias_name,
            alias_type=excluded.alias_type,
            domain=COALESCE(
                excluded.domain,
                employer_identity_aliases.domain
            ),
            confidence=MAX(
                employer_identity_aliases.confidence,
                excluded.confidence
            ),
            source=excluded.source
        """,
        (
            parent_key,
            alias_name,
            normalized,
            alias_type,
            domain,
            confidence,
            source,
        ),
    )

    return True


def load_sponsor_universe(conn):
    if not table_exists(
        conn,
        "combined_sponsor_universe",
    ):
        print(
            "SPONSOR UNIVERSE: unavailable"
        )
        return 0

    cols = columns(
        conn,
        "combined_sponsor_universe",
    )

    name_col = next(
        (
            col
            for col in (
                "display_name",
                "employer_name",
                "name",
            )
            if col in cols
        ),
        None,
    )

    if not name_col:
        raise RuntimeError(
            "combined_sponsor_universe "
            "has no employer-name column"
        )

    parent_expr = (
        "parent_key"
        if "parent_key" in cols
        else "NULL"
    )

    matched_expr = (
        "matched_employer_id"
        if "matched_employer_id" in cols
        else "NULL"
    )

    rows = conn.execute(
        f"""
        SELECT
            {name_col} AS display_name,
            {parent_expr} AS parent_key,
            {matched_expr} AS matched_employer_id
        FROM combined_sponsor_universe
        WHERE {name_col} IS NOT NULL
        """
    ).fetchall()

    loaded = 0

    for row in rows:
        name = (
            row["display_name"]
            or ""
        ).strip()

        if not name:
            continue

        parent_key = row["parent_key"]

        if not parent_key:
            # Stable fallback for sponsor records
            # without an explicit parent grouping.
            parent_key = (
                "SPONSOR:"
                + normalize_name(name)
            )

        upsert_identity(
            conn,
            identity_key=parent_key,
            canonical_name=name,
            sponsor_parent_key=parent_key,
            registry_employer_id=row[
                "matched_employer_id"
            ],
        )

        add_alias(
            conn,
            parent_key=parent_key,
            alias_name=name,
            alias_type="SPONSOR_NAME",
            confidence=1.0,
            source="COMBINED_SPONSOR_UNIVERSE",
        )

        loaded += 1

    return loaded


def load_registry(conn):
    if not table_exists(
        conn,
        "employers",
    ):
        print(
            "REGISTRY EMPLOYERS: unavailable"
        )
        return 0

    employer_cols = columns(
        conn,
        "employers",
    )

    id_col = (
        "id"
        if "id" in employer_cols
        else None
    )

    name_col = next(
        (
            col
            for col in (
                "display_name",
                "name",
                "company_name",
            )
            if col in employer_cols
        ),
        None,
    )

    careers_col = (
        "careers_url"
        if "careers_url" in employer_cols
        else None
    )

    if not id_col or not name_col:
        raise RuntimeError(
            "Unsupported employers schema"
        )

    careers_expr = (
        careers_col
        if careers_col
        else "NULL"
    )

    rows = conn.execute(
        f"""
        SELECT
            {id_col} AS employer_id,
            {name_col} AS display_name,
            {careers_expr} AS careers_url
        FROM employers
        """
    ).fetchall()

    loaded = 0

    for row in rows:
        employer_id = row[
            "employer_id"
        ]

        name = (
            row["display_name"]
            or ""
        ).strip()

        if not name:
            continue

        # ==================================================
        # First preference:
        # sponsor universe already explicitly linked
        # this registry employer.
        # ==================================================

        sponsor = None

        if table_exists(
            conn,
            "combined_sponsor_universe",
        ):
            sponsor_cols = columns(
                conn,
                "combined_sponsor_universe",
            )

            if (
                "matched_employer_id"
                in sponsor_cols
                and "parent_key"
                in sponsor_cols
            ):
                sponsor = conn.execute(
                    """
                    SELECT parent_key
                    FROM combined_sponsor_universe
                    WHERE matched_employer_id=?
                      AND parent_key IS NOT NULL
                    ORDER BY
                        combined_sponsor_score DESC
                    LIMIT 1
                    """,
                    (employer_id,),
                ).fetchone()

        if sponsor:
            identity_key = sponsor[
                "parent_key"
            ]
            sponsor_parent_key = (
                identity_key
            )

        else:
            identity_key = (
                f"REGISTRY:{employer_id}"
            )
            sponsor_parent_key = None

        domain = domain_from_url(
            row["careers_url"]
        )

        upsert_identity(
            conn,
            identity_key=identity_key,
            canonical_name=name,
            sponsor_parent_key=(
                sponsor_parent_key
            ),
            registry_employer_id=(
                employer_id
            ),
            primary_domain=domain,
        )

        add_alias(
            conn,
            parent_key=identity_key,
            alias_name=name,
            alias_type="REGISTRY_NAME",
            domain=domain,
            confidence=1.0,
            source="EMPLOYERS",
        )

        loaded += 1

    return loaded


def load_source_domains(conn):
    if not table_exists(
        conn,
        "employer_sources",
    ):
        return 0

    cols = columns(
        conn,
        "employer_sources",
    )

    if (
        "employer_id" not in cols
        or "careers_url" not in cols
    ):
        return 0

    rows = conn.execute(
        """
        SELECT
            employer_id,
            careers_url
        FROM employer_sources
        WHERE careers_url IS NOT NULL
        """
    ).fetchall()

    loaded = 0

    for row in rows:
        domain = domain_from_url(
            row["careers_url"]
        )

        if not domain:
            continue

        identity = conn.execute(
            """
            SELECT
                id,
                identity_key,
                canonical_name
            FROM employer_identities
            WHERE registry_employer_id=?
            LIMIT 1
            """,
            (
                row["employer_id"],
            ),
        ).fetchone()

        if not identity:
            continue

        conn.execute(
            """
            UPDATE employer_identities
            SET
                primary_domain=
                    COALESCE(
                        primary_domain,
                        ?
                    ),
                updated_at=
                    CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (
                domain,
                identity["id"],
            ),
        )

        add_alias(
            conn,
            parent_key=identity[
                "identity_key"
            ],
            alias_name=identity[
                "canonical_name"
            ],
            alias_type="CAREERS_DOMAIN",
            domain=domain,
            confidence=0.95,
            source="EMPLOYER_SOURCES",
        )

        loaded += 1

    return loaded


def main():
    with get_connection() as conn:
        create_schema(conn)

        # Sponsor identities first.
        sponsors = load_sponsor_universe(
            conn
        )

        # Registry employers then attach to
        # already-known sponsor identities where possible.
        registry = load_registry(
            conn
        )

        domains = load_source_domains(
            conn
        )

        conn.commit()

        identity_count = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM employer_identities
            """
        ).fetchone()["n"]

        alias_count = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM employer_identity_aliases
            """
        ).fetchone()["n"]

        sponsor_linked = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM employer_identities
            WHERE sponsor_parent_key
                  IS NOT NULL
            """
        ).fetchone()["n"]

        registry_linked = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM employer_identities
            WHERE registry_employer_id
                  IS NOT NULL
            """
        ).fetchone()["n"]

        both = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM employer_identities
            WHERE sponsor_parent_key
                  IS NOT NULL
              AND registry_employer_id
                  IS NOT NULL
            """
        ).fetchone()["n"]

    print()
    print("=" * 80)
    print(
        "EMPLOYER IDENTITY GRAPH COMPLETE"
    )
    print("=" * 80)

    print(
        "SPONSOR ROWS PROCESSED:",
        sponsors,
    )

    print(
        "REGISTRY ROWS PROCESSED:",
        registry,
    )

    print(
        "SOURCE DOMAINS PROCESSED:",
        domains,
    )

    print()

    print(
        "CANONICAL IDENTITIES:",
        identity_count,
    )

    print(
        "ALIASES:",
        alias_count,
    )

    print(
        "SPONSOR-LINKED:",
        sponsor_linked,
    )

    print(
        "REGISTRY-LINKED:",
        registry_linked,
    )

    print(
        "REGISTRY + SPONSOR:",
        both,
    )


if __name__ == "__main__":
    main()
