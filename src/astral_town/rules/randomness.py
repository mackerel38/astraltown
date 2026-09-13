"""One distribution API shared by exact and seeded sampling paths."""

from fractions import Fraction
from math import lcm

from astral_town.model.outcomes import WeightedOutcome, validate_distribution


def configured_distribution(registry, key, state=None):
    rows = registry.distribution(key,state) if state is not None else registry.require(key)
    return validate_distribution(WeightedOutcome(Fraction(row["probability"]), row["value"]) for row in rows)


def sample(outcomes, rng):
    outcomes = validate_distribution(outcomes)
    denominator = lcm(*(o.probability.denominator for o in outcomes))
    ticket = rng.randrange(denominator)
    total = 0
    for outcome in outcomes:
        total += outcome.probability.numerator * (denominator // outcome.probability.denominator)
        if ticket < total:
            return outcome
    raise AssertionError("Validated probabilities must exhaust the interval")
