from __future__ import annotations


HYBRID_CONFIGS = {
    "Apple": {
        "discovery": {
            "type": "HTML_LINKS",
            "url": "https://jobs.apple.com/en-us/search",
            "fixed_country": "United States",

            "params": {
                "location": "united-states-USA",
                "page": "{page}",
            },

            "max_pages": 12,

            "link_contains": "/details/",

            # First group = base requisition number.
            "id_regex": r"/details/(\d+)(?:-[^/]+)?/",

            # Preserve full public Apple posting identifier.
            "external_id_regex": r"/details/([^/]+)/",

            "container_markers": [
                "Role Number:",
                "Location",
            ],

            "location_patterns": [
                r".*\bLocation\s+(.+?)\s+Actions\b",
                r"\bLocation\s+(.+?)\s+See full role description\b",
                r"\bLocation\s+(.+?)\s+Share\b",
                r"\bLocation\s+(.+?)\s+Role Number:",
            ],

            "date_regex": (
                r"\b("
                r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
                r")\s+\d{1,2},\s+\d{4}\b"
            ),

            "date_format": "%b %d, %Y",

            # Preserve enough card text for fallback analysis.
            "excerpt_limit": 8000,
        },

        "detail": {
            "type": "JSON_API",

            "method": "GET",

            "url": (
                "https://jobs.apple.com/"
                "api/v1/jobDetails/{job_id}"
            ),

            "job_id_template": "REQ-{id}",

            "root_path": "res",

            # Apple can block bulk enrichment without blocking
            # the actual public search pages.
            "blocked_statuses": [429, 436],

            "delay_seconds": 1.25,

            "title_path": "postingTitle",

            "external_id_paths": [
                "jobNumber",
                "reqId",
                "id",
            ],

            "published_paths": [
                "longPostingDate",
                "postDateInGMT",
                "postingDateMeta",
            ],

            "description_paths": [
                "jobSummary",
                "description",
                "responsibilities",
                "minimumQualifications",
                "preferredQualifications",
                "additionalRequirements",
                "educationExperience",
            ],

            "location_list_path": "locations",

            "location_fields": [
                "city",
                "stateProvince",
                "countryName",
            ],
        },
    },
}
