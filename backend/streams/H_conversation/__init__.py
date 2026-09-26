"""V1 compatibility exports. Current product code imports .service explicitly."""

from .legacy import ConversationService, DateRequest, FeedbackRequest, MockConstraintParser

__all__ = ["ConversationService", "DateRequest", "FeedbackRequest", "MockConstraintParser"]
