from .jobs_repository import _conn

def mark_source_lifecycle(company_name, source_name, seen_urls):
    seen = {u for u in (seen_urls or set()) if u}
    with _conn() as conn:
        rows = conn.execute("SELECT id, source_url FROM jobs WHERE company_name_raw=? AND source=?", (company_name, source_name)).fetchall()
        active = disappeared = 0
        for row in rows:
            if row["source_url"] in seen:
                conn.execute("UPDATE jobs SET is_active=1,last_verified_at=CURRENT_TIMESTAMP,disappeared_at=NULL WHERE id=?", (row["id"],))
                active += 1
            else:
                conn.execute("UPDATE jobs SET is_active=0,disappeared_at=COALESCE(disappeared_at,CURRENT_TIMESTAMP) WHERE id=?", (row["id"],))
                disappeared += 1
        conn.commit()
    return {"active": active, "disappeared": disappeared}
