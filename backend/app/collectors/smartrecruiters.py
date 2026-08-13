from .base import BaseCollector

class SmartRecruitersCollector(BaseCollector):
    ats_name = "SMARTRECRUITERS"
    def fetch(self, source):
        raise RuntimeError(
            "SmartRecruiters adapter not enabled yet: company-specific public access must be verified before collection."
        )
