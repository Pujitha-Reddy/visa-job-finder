from .greenhouse import GreenhouseCollector
from .lever import LeverCollector
from .ashby import AshbyCollector
from .smartrecruiters import SmartRecruitersCollector
from .workable import WorkableCollector
from .workday import WorkdayCollector
from .custom_html import CustomHTMLCollector
from .insight_global import InsightGlobalCollector
from .kforce import KforceCollector
from .teksystems import TEKsystemsCollector
from .randstad import RandstadCollector
from .robert_half import RobertHalfCollector

COLLECTORS = {
    "GREENHOUSE": GreenhouseCollector(),
    "LEVER": LeverCollector(),
    "ASHBY": AshbyCollector(),
    "SMARTRECRUITERS": SmartRecruitersCollector(),
    "WORKABLE": WorkableCollector(),
    "WORKDAY": WorkdayCollector(),
    "CUSTOM_HTML": CustomHTMLCollector(),
    "INSIGHT_GLOBAL": InsightGlobalCollector(),
    "KFORCE": KforceCollector(),
    "TEKSYSTEMS": TEKsystemsCollector(),
    "RANDSTAD": RandstadCollector(),
    "ROBERT_HALF": RobertHalfCollector(),
}

def get_collector(ats):
    return COLLECTORS.get((ats or "").upper())
