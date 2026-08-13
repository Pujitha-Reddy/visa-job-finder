from .registry.repository import conn, init_registry

AUTO_ATS = ("GREENHOUSE","LEVER","ASHBY","WORKABLE")

def main():
    init_registry()
    with conn() as c:
        rows = c.execute("""
            SELECT id, ats, token
            FROM employer_sources
            WHERE ats IN ('GREENHOUSE','LEVER','ASHBY','WORKABLE')
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
                    notes='Disabled by V7.6.1: zero-job guessed ATS slug is insufficient verification.'
                WHERE id=?
            """, (source_id,))
        c.commit()

    print({"disabled_zero_job_auto_sources": len(ids)})

if __name__ == "__main__":
    main()
