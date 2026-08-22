from __future__ import annotations

import os
from contextlib import contextmanager

from app.database import get_connection
from app.postgres_repository import pg_conn


def backend_name():
    """
    Explicit override:
        CANONICAL_DB_BACKEND=sqlite
        CANONICAL_DB_BACKEND=postgres

    Otherwise:
        DATABASE_URL present -> postgres
        no DATABASE_URL      -> sqlite
    """

    override = (
        os.getenv(
            "CANONICAL_DB_BACKEND",
            "",
        )
        .strip()
        .lower()
    )

    if override in {
        "sqlite",
        "postgres",
    }:
        return override

    return (
        "postgres"
        if os.getenv("DATABASE_URL")
        else "sqlite"
    )


def use_postgres():
    return (
        backend_name()
        == "postgres"
    )


@contextmanager
def canonical_conn():
    if use_postgres():
        with pg_conn() as conn:
            yield conn
    else:
        with get_connection() as conn:
            yield conn


def adapt_sql(query: str):
    """
    Translate the small set of SQL dialect differences
    used by V110.
    """

    if not use_postgres():
        return query

    # ---------------------------------------------
    # Parameter placeholders
    # ---------------------------------------------

    query = query.replace(
        "?",
        "%s",
    )

    # ---------------------------------------------
    # SQLite integer booleans -> PostgreSQL booleans
    # ---------------------------------------------

    replacements = {
        "j.is_active=1":
            "j.is_active=TRUE",

        "j.is_active = 1":
            "j.is_active = TRUE",

        "e.is_software_role=1":
            "e.is_software_role=TRUE",

        "e.is_software_role = 1":
            "e.is_software_role = TRUE",

        "e.is_eligible=1":
            "e.is_eligible=TRUE",

        "e.is_eligible = 1":
            "e.is_eligible = TRUE",

        "e.is_us_job=1":
            "e.is_us_job=TRUE",

        "e.is_us_job = 1":
            "e.is_us_job = TRUE",

        "e.is_us_remote=1":
            "e.is_us_remote=TRUE",

        "e.is_us_remote = 1":
            "e.is_us_remote = TRUE",

        "s.is_active=1":
            "s.is_active=TRUE",

        "s.is_active = 1":
            "s.is_active = TRUE",
    }

    for old, new in replacements.items():
        query = query.replace(
            old,
            new,
        )

    return query
