"""State-dependent exact distributions. Strategies are configuration, not evidence."""

from fractions import Fraction
from itertools import combinations, product
from math import comb

from astral_town.model.enums import BuildingType, StandType, Pack
from astral_town.model.outcomes import WeightedOutcome, validate_distribution
from .catalog import eligible, required_packs
from .stand_catalog import stand_eligible


def strategy_distribution(registry, specification, state):
    strategy = specification.get("strategy")
    if strategy == "uniform_eligible_stands":
        kinds = tuple(StandType(k) for k in specification.get("types", StandType))
        if len(set(kinds)) != len(kinds):raise ValueError("Duplicate stand type in distribution pool")
        pool = tuple(kind for kind in kinds if stand_eligible(kind, state.selected_packs, registry))
        # Ownership legality stays in SELECT_STAND, under its separate configured rule.
        count = specification["count"]
        if type(count) is not int or count < 1:raise ValueError("Invalid stand offer count")
        if not pool:raise ValueError("No eligible stands for offer strategy")
        count = min(count, len(pool))
        # Enum order is stable; no permutations of the same choice menu.
        return validate_distribution(WeightedOutcome(Fraction(1, comb(len(pool), count)), tuple(k.value for k in subset))
                                     for subset in combinations(pool, count))
    if strategy == "uniform_eligible_buildings":
        kinds = tuple(BuildingType(k) for k in specification.get("types", BuildingType))
        if len(set(kinds)) != len(kinds):raise ValueError("Duplicate building type in distribution pool")
        pool = tuple(kind for kind in kinds if eligible(kind, state.selected_packs, registry))
        if "required_pack" in specification:
            pack = Pack(specification["required_pack"])
            pool = tuple(kind for kind in pool if pack in required_packs(kind, registry))
        if not pool:raise ValueError("No eligible buildings for distribution strategy")
        template = registry.require(specification["template_rule"])
        templates = tuple(dict(template, building_type=kind.value) for kind in pool)
        if "slots" not in specification:
            return validate_distribution(WeightedOutcome(Fraction(1, len(pool)), row) for row in templates)
        slots = specification["slots"]
        if type(slots) is not int or slots < 1:raise ValueError("Invalid shop slot count")
        prices = registry.require(specification["prices_rule"])
        offers = tuple({"building": row, "price": prices[registry.require(f"{kind.value}.rarity")]}
                       for kind, row in zip(pool, templates))
        # Independent ordered slots preserve slot marginals and existing explicit shop semantics.
        return validate_distribution(WeightedOutcome(Fraction(1, len(pool)**slots), rows)
                                     for rows in product(offers, repeat=slots))
    raise ValueError(f"Unknown distribution strategy: {strategy}")
