"""Calculation resource limits, independent of missing game rules."""


class SearchBudgetExceeded(Exception):
    """The configured search or trajectory budget has been exhausted."""
