from __future__ import annotations

from .database import get_connection


COLUMNS = {
    "tax_id": "TEXT",
    "naics_code": "TEXT",

    "new_employment_approvals": "INTEGER NOT NULL DEFAULT 0",
    "new_employment_denials": "INTEGER NOT NULL DEFAULT 0",

    "continuation_approvals": "INTEGER NOT NULL DEFAULT 0",
    "continuation_denials": "INTEGER NOT NULL DEFAULT 0",

    "same_employer_approvals": "INTEGER NOT NULL DEFAULT 0",
    "same_employer_denials": "INTEGER NOT NULL DEFAULT 0",

    "new_concurrent_approvals": "INTEGER NOT NULL DEFAULT 0",
    "new_concurrent_denials": "INTEGER NOT NULL DEFAULT 0",

    "change_employer_approvals": "INTEGER NOT NULL DEFAULT 0",
    "change_employer_denials": "INTEGER NOT NULL DEFAULT 0",

    "amended_approvals": "INTEGER NOT NULL DEFAULT 0",
    "amended_denials": "INTEGER NOT NULL DEFAULT 0",
}


def main():
    with get_connection() as conn:
        existing = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(uscis_h1b_employer_history)"
            ).fetchall()
        }

        for name, definition in COLUMNS.items():
            if name not in existing:
                conn.execute(
                    f"""
                    ALTER TABLE uscis_h1b_employer_history
                    ADD COLUMN {name} {definition}
                    """
                )
                print("ADDED:", name)

        conn.commit()

    print("V9.6 USCIS detail migration complete.")


if __name__ == "__main__":
    main()
