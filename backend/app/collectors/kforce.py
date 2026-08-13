from .base import BaseCollector

class KforceCollector(BaseCollector):
    ats_name = "KFORCE"
    def fetch(self, source):
        raise RuntimeError("Official Kforce search/visa pages verified; extraction path still dynamic.")
