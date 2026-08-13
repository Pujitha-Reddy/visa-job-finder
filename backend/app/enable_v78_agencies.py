from .registry.repository import conn, init_registry, upsert_source

SOURCES = [
    (
        "Randstad Digital",
        "RANDSTAD",
        "https://www.randstadusa.com/jobs/q-software-engineer/remote/",
        "V7.8 official Randstad USA remote software-job collector."
    ),
    (
        "Robert Half",
        "ROBERT_HALF",
        "https://www.roberthalf.com/us/en/jobs/all/software-engineer?remote=Yes",
        "V7.8 official Robert Half remote software-job collector."
    ),
]

def main():
    init_registry()
    results = {}

    for company, ats, url, note in SOURCES:
        with conn() as c:
            row = c.execute(
                "SELECT id FROM employers WHERE lower(display_name)=lower(?)",
                (company,)
            ).fetchone()

        if not row:
            results[company] = False
            continue

        upsert_source(row["id"], ats, None, url, True, note)

        with conn() as c:
            c.execute("""
                UPDATE employer_sources
                SET source_verified=1, enabled=1
                WHERE employer_id=? AND ats=?
            """, (row["id"], ats))
            c.commit()

        results[company] = True

    print(results)

if __name__ == "__main__":
    main()
