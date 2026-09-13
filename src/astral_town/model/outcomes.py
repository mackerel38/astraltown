from dataclasses import dataclass
from fractions import Fraction
from typing import Generic, TypeVar

from .events import EventLogEntry

T = TypeVar("T")


@dataclass(frozen=True)
class WeightedOutcome(Generic[T]):
    probability: Fraction
    state: T
    events: tuple[EventLogEntry, ...] = ()

    def __post_init__(self):
        if not isinstance(self.probability, Fraction) or not 0 < self.probability <= 1:
            raise ValueError("Probability must be an exact Fraction in (0, 1]")


def validate_distribution(outcomes):
    outcomes = tuple(outcomes)
    if sum((o.probability for o in outcomes), Fraction()) != 1:
        raise ValueError("Chance probabilities must sum to 1")
    return outcomes
