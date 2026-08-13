from abc import ABC, abstractmethod

class BaseCollector(ABC):
    ats_name = "BASE"

    @abstractmethod
    def fetch(self, source: dict) -> list[dict]:
        raise NotImplementedError
