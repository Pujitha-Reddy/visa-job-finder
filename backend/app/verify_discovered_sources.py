from __future__ import annotations

import requests


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/150 Safari/537.36"
    )
}


def verify_workday(host: str, site: str):
    url = f"https://{host}/wday/cxs/{host.split('.')[0]}/{site}/jobs"

    try:
        r = requests.post(
            url,
            headers={
                **HEADERS,
                "Content-Type": "application/json",
            },
            json={
                "appliedFacets": {},
                "limit": 20,
                "offset": 0,
                "searchText": "",
            },
            timeout=25,
        )

        print("WORKDAY")
        print("URL:", url)
        print("STATUS:", r.status_code)
        print("TYPE:", r.headers.get("content-type"))
        print("SIZE:", len(r.content))

        if r.ok:
            data = r.json()
            print("TOTAL:", data.get("total"))
            print("ROWS:", len(data.get("jobPostings") or []))

        print()

    except Exception as exc:
        print("WORKDAY ERROR:", exc)


def verify_eightfold(domain: str):
    session = requests.Session()
    session.headers.update(HEADERS)

    careers = (
        "https://app.eightfold.ai/careers"
        f"?domain={domain}"
    )

    try:
        r = session.get(
            careers,
            timeout=25,
            allow_redirects=True,
        )

        print("EIGHTFOLD")
        print("CAREERS:", careers)
        print("STATUS:", r.status_code)
        print("FINAL:", r.url)
        print("SIZE:", len(r.content))

        csrf = (
            session.cookies.get("csrftoken")
            or session.cookies.get("csrf")
        )

        print("CSRF:", bool(csrf))
        print()

    except Exception as exc:
        print("EIGHTFOLD ERROR:", exc)


def main():
    # Expedia candidate discovered from branded careers page.
    #
    # We don't know the exact CXS tenant/site yet,
    # so try likely site values separately after confirming host.
    verify_workday(
        "expedia.wd108.myworkdayjobs.com",
        "search",
    )

    # Applied Materials Eightfold candidate.
    verify_eightfold(
        "appliedmaterials.com"
    )


if __name__ == "__main__":
    main()