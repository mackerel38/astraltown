"""Exact ordered dice outcomes; modifier consumption must be configured."""

from dataclasses import replace
from fractions import Fraction
from itertools import product

from astral_town.model.enums import ActivationCause, EventType, TriggerCardinality
from astral_town.model.events import Event
from astral_town.model.outcomes import WeightedOutcome, validate_distribution
from .registry import UnresolvedRule


def dice_outcomes(state, registry):
    rows=registry.require("natural_die_distribution")
    natural=tuple((row["face"],Fraction(row["probability"])) for row in rows)
    if len({face for face,_ in natural})!=len(natural) or any(type(face) is not int or face not in range(1,7) for face,_ in natural):
        raise ValueError("Invalid natural die faces")
    validate_distribution(WeightedOutcome(probability,face) for face,probability in natural)
    remaining = state.forced_die_effects
    fixed = None
    if remaining:
        top_priority = max(effect.priority for effect in remaining)
        winners = tuple(effect for effect in remaining if effect.priority == top_priority)
        if len(winners) != 1:
            raise UnresolvedRule("forced_die_tie_order")
        winner = winners[0]
        policy = registry.require("forced_die_consumption")
        if policy == "all":
            remaining = ()
        elif policy == "winner":
            remaining = tuple(effect for effect in remaining if effect is not winner)
        else:
            raise ValueError("forced_die_consumption must be all or winner")
        fixed = winner.face
        if state.next_dice_count == 2:
            index = registry.require("forced_die_index")
            if index not in (0, 1):
                raise ValueError("Invalid forced die index")
        else:
            index = 0
    domains = tuple(((fixed,Fraction(1)),) if fixed is not None and i == index else natural
                    for i in range(state.next_dice_count))
    outcomes=[]
    for dice in product(*domains):
        probability=Fraction(1)
        for _,weight in dice:probability*=weight
        outcomes.append(WeightedOutcome(probability,replace(state,last_roll=tuple(face for face,_ in dice),roll_id=state.roll_id+1,
                                                           next_dice_count=1,forced_die_effects=remaining,forced_stop=False)))
    return validate_distribution(outcomes)


def trigger_events(state, source_id, faces, cardinality, *, effect_id="dice"):
    indices = tuple(i for i, face in enumerate(state.last_roll) if face in faces)
    if cardinality == TriggerCardinality.PER_ROLL:
        return (Event(EventType.ROLL_CONDITION, source_id, ActivationCause.NATURAL_DIE,
                      state.roll_id, payload=(("effect_id", effect_id),)),) if indices else ()
    if cardinality != TriggerCardinality.PER_DIE:
        raise ValueError("Trigger cardinality must be explicit")
    return tuple(Event(EventType.DIE_FACE, source_id, ActivationCause.NATURAL_DIE,
                       state.roll_id, i, (("face", state.last_roll[i]), ("effect_id", effect_id))) for i in indices)
