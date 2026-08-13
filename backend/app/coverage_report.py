from .registry.repository import conn, init_registry

def main():
    init_registry()
    with conn() as c:
        total = c.execute("SELECT COUNT(*) c FROM employers").fetchone()["c"]
        verified = c.execute("""
            SELECT COUNT(DISTINCT employer_id) c
            FROM employer_sources WHERE source_verified=1
        """).fetchone()["c"]
        active = c.execute("""
            SELECT COUNT(DISTINCT employer_id) c
            FROM employer_sources WHERE source_verified=1 AND enabled=1
        """).fetchone()["c"]

        by_ats = [dict(r) for r in c.execute("""
            SELECT ats,
                   COUNT(DISTINCT employer_id) employers,
                   SUM(CASE WHEN source_verified=1 THEN 1 ELSE 0 END) verified_sources,
                   SUM(active_jobs) active_jobs
            FROM employer_sources
            GROUP BY ats
            ORDER BY verified_sources DESC
        """).fetchall()]

        unresolved = [r["display_name"] for r in c.execute("""
            SELECT e.display_name
            FROM employers e
            WHERE NOT EXISTS (
                SELECT 1 FROM employer_sources es
                WHERE es.employer_id=e.id AND es.source_verified=1
            )
            ORDER BY e.display_name
        """).fetchall()]

    print({
        "employers_seeded": total,
        "employers_verified": verified,
        "employers_active": active,
        "coverage_percent": round((verified/total*100), 1) if total else 0,
        "by_ats": by_ats,
        "unresolved_count": len(unresolved),
    })

    if unresolved:
        print("\nUNRESOLVED EMPLOYERS:")
        for name in unresolved:
            print("-", name)

if __name__ == "__main__":
    main()
