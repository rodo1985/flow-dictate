"""Top-level package for the flow-dictate scaffold."""

from flow_dictate.config import AppConfig
from flow_dictate.service import DictationService, ServiceRunResult

__all__ = ["AppConfig", "DictationService", "ServiceRunResult"]
