from .registry.repository import conn, init_registry, upsert_source

def main():
    init_registry()
    with conn() as c:
        row = c.execute(
            "SELECT id FROM employers WHERE lower(display_name)=lower('Insight Global')"
        ).fetchone()

    if not row:
        print({"insight_global_enabled": False, "reason":"Employer not found"})
        return

    upsert_source(
        row["id"],
        "INSIGHT_GLOBAL",
        None,
        "https://jobs.insightglobal.com/jobs/find_a_job/?miles=False&remote=true&srch=remote",
        True,
        "V7.7 verified public Insight Global job-board collector."
    )
    with conn() as c:
        c.execute("""
            UPDATE employer_sources
            SET source_verified=1, enabled=1
            WHERE employer_id=? AND ats='INSIGHT_GLOBAL'
        """, (row["id"],))
        c.commit()

    print({"insight_global_enabled": True})

if __name__ == "__main__":
    main()
