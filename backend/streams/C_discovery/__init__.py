"""V1 compatibility exports. Current product code imports .service explicitly."""

from .legacy import ActivityListing, DiscoveryConstraints
from .legacy import ActivityRepository, LocalActivityRepository
from .legacy import DiscoveryService

__all__ = ["ActivityListing", "DiscoveryConstraints", "ActivityRepository",
           "LocalActivityRepository", "DiscoveryService"]
