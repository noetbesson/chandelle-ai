"""V1 compatibility exports. Current product code imports .service explicitly."""

from .legacy import OpportunityDecision, ProactiveCheck, ProactiveService

__all__ = ["OpportunityDecision", "ProactiveCheck", "ProactiveService"]
