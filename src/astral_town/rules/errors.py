class IllegalAction(ValueError):
    """Legal state/configuration, but the requested player action is unavailable."""


class CalculationCancelled(Exception):
    """Cooperative cancellation shared by rules and search."""
