from .base import BaseCollector

class WorkdayCollector(BaseCollector):
    ats_name = "WORKDAY"
    def fetch(self, source):
        raise RuntimeError(
            "Workday adapter requires a verified tenant career-site endpoint; generic collection is intentionally disabled."
        )
