from .base import BaseCollector

class TEKsystemsCollector(BaseCollector):
    ats_name = "TEKSYSTEMS"
    def fetch(self, source):
        raise RuntimeError("TEKsystems public careers site verified; search rendering is dynamic.")
