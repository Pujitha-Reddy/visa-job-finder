from __future__ import annotations

from app.database import get_connection
from app.postgres_repository import pg_conn

from app.migrate_v119_cloud_state import (
    create_cloud_tables,
    preflight_registry,
    sync_employers,
    sync_sources,
    sync_discovery,
)


def main():
    print("=" * 110)
    print("V119.9B EPHEMERAL RUNNER -> POSTGRES STATE SYNC")
    print("=" * 110)

    with get_connection() as sqlite:
        with pg_conn() as pg, pg.cursor() as cur:

            create_cloud_tables(cur)

            preflight_registry(
                sqlite,
                cur,
            )

            employers = sync_employers(
                sqlite,
                cur,
            )

            sources = sync_sources(
                sqlite,
                cur,
            )

            discovery = sync_discovery(
                sqlite,
                cur,
            )

            pg.commit()

    print()
    print("EMPLOYERS:", employers)
    print("EMPLOYER SOURCES:", sources)
    print("DISCOVERY ROWS:", discovery)

    print()
    print("=" * 110)
    print("V119.9B STATE SYNC COMPLETE")
    print("=" * 110)


if __name__ == "__main__":
    main()
