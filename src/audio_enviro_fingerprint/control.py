"""Cooperative analysis cancellation shared by UI-independent modules."""


class AnalysisCancelled(ValueError):
    """Requested cancellation; no partial analysis result should be published."""


def check_cancelled(should_cancel=None):
    if should_cancel is not None and should_cancel():
        raise AnalysisCancelled('Analysis cancelled')
