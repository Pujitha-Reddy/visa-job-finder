from .greenhouse import GreenhouseCollector
from .lever import LeverCollector
from .ashby import AshbyCollector
from .smartrecruiters import SmartRecruitersCollector
from .workable import WorkableCollector
from .workday import WorkdayCollector
from .eightfold import EightfoldCollector
from .oracle_hcm import OracleHCMCollector
from .custom_html import CustomHTMLCollector
from .insight_global import InsightGlobalCollector
from .kforce import KforceCollector
from .teksystems import TEKsystemsCollector
from .randstad import RandstadCollector
from .robert_half import RobertHalfCollector
from .amazon import AmazonCollector
from .apple import AppleCollector
from .hybrid import HybridCollector
from .radancy import RadancyCollector
from .adp import ADPCollector
from .radancy_sas import RadancySearchServiceCollector
from .generic_jobs import GenericJobCollector

COLLECTORS = {
    "HYBRID": HybridCollector(),
    "GREENHOUSE": GreenhouseCollector(),
    "LEVER": LeverCollector(),
    "ASHBY": AshbyCollector(),
    "SMARTRECRUITERS": SmartRecruitersCollector(),
    "WORKABLE": WorkableCollector(),
    "WORKDAY": WorkdayCollector(),
    "EIGHTFOLD": EightfoldCollector(),
    "ORACLE_HCM": OracleHCMCollector(),
    "CUSTOM_HTML": CustomHTMLCollector(),
    "INSIGHT_GLOBAL": InsightGlobalCollector(),
    "KFORCE": KforceCollector(),
    "TEKSYSTEMS": TEKsystemsCollector(),
    "RANDSTAD": RandstadCollector(),
    "ROBERT_HALF": RobertHalfCollector(),
    "AMAZON": AmazonCollector(),
    "RADANCY": RadancyCollector(),
    "APPLE": AppleCollector(),
    "ADP": ADPCollector(),
    "RADANCY_SAS": RadancySearchServiceCollector(),
    "GENERIC": GenericJobCollector(),
}


def get_collector(ats):
    return COLLECTORS.get((ats or "").upper())
