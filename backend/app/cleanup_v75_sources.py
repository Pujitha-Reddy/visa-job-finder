from .registry.repository import conn, init_registry

def main():
    init_registry()
    with conn() as c:
        rows = c.execute("""
            SELECT id, employer_id, ats, token, active_jobs, notes
            FROM employer_sources
            WHERE ats='WORKABLE'
              AND source_verified=1
              AND COALESCE(active_jobs,0)=0
              AND notes LIKE '%Auto-discovered%'
        """).fetchall()

        ids = [r["id"] for r in rows]
        for source_id in ids:
            c.execute("""
                UPDATE employer_sources
                SET source_verified=0,
                    enabled=0,
                    notes='Disabled by V7.5: zero-job auto-discovery is insufficient verification.'
                WHERE id=?
            """, (source_id,))
        c.commit()

    print({"disabled_zero_job_workable_sources": len(ids)})

if __name__ == "__main__":
    main()
