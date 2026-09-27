"""Compatibility boundary: the former disk catalogue has been retired."""
def load_activities():
    raise RuntimeError('Use the authenticated /api/v2/dates/search pipeline; no disk catalogue remains.')
