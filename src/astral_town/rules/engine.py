"""Structured FIFO event dispatch with complete immutable transition logs.

Handlers return weighted states and follow-up events. Follow-ups resolve before
the next sibling event, preserving causality without recursive Python calls.
The order of supplied root events is explicit, not a claim about unknown game order.
"""

from dataclasses import dataclass, replace
from fractions import Fraction

from astral_town.model.events import Event, EventLogEntry
from astral_town.model.enums import EventType as E
from astral_town.model.outcomes import WeightedOutcome, validate_distribution
from astral_town.model.state import ForcedDieEffect
from . import economy


@dataclass(frozen=True)
class Transition:
    state: object
    followups: tuple[Event, ...] = ()


def deterministic(state, *events):
    return (WeightedOutcome(Fraction(1), Transition(state, tuple(events))),)


class EventEngine:
    def __init__(self, registry, *, max_events=10000):
        self.registry = registry
        self.max_events = max_events
        self.cancel = None
        self.handlers = {}
        self._install_primitives()

    def register(self, event_type, handler):
        if event_type in self.handlers:
            raise ValueError(f"Handler already registered: {event_type}")
        self.handlers[event_type] = handler

    def _install_primitives(self):
        self.handlers.update({
            E.GAIN_COIN: lambda s, e: deterministic(economy.gain_coin(s, e.get("amount"), counts_for_progress=e.get("progress", False))),
            E.SPEND_COIN: lambda s, e: deterministic(economy.spend_coin(s, e.get("amount"))),
            E.GAIN_XP: lambda s, e: deterministic(s.with_building(economy.gain_xp(s.building(e.source_id), e.get("amount"), self.registry))),
            E.REMOVE_BUILDING: lambda s, e: deterministic(economy.remove_building(s, e.source_id)),
            E.ADD_BUILDING: lambda s, e: deterministic(economy.add_building(s, e.get("building"), self.registry)),
            E.PLACE_BUILDING: lambda s, e: deterministic(economy.place_building(s, e.source_id, e.get("location"), self.registry)),
            E.MOVE_BUILDING: lambda s, e: deterministic(economy.place_building(s, e.source_id, e.get("location"), self.registry)),
            E.MERGE_BUILDING: lambda s, e: deterministic(economy.merge_buildings(s, e.source_id, e.get("material"), self.registry)),
            E.BONUS: self._bonus,
            E.STAND_CHARGE: self._charge,
            E.FORCED_STOP: lambda s, e: deterministic(replace(s, forced_stop=True, movement_remaining=0)),
            E.SET_FUTURE_DIE: self._future_die,
        })

    def _bonus(self, state, event):
        field = event.get("field")
        allowed = {"dice_coin_bonus", "pass_coin_bonus", "stay_coin_bonus", "wish_stage_bonus", "captain_pass_bonus", "treasure_decay"}
        if field not in allowed or type(event.get("amount")) is not int:
            raise ValueError("Invalid permanent bonus")
        building = state.building(event.source_id)
        return deterministic(state.with_building(replace(building, **{field: getattr(building, field) + event.get("amount")})))

    def _charge(self, state, event):
        if not any(s.instance_id == event.source_id for s in state.stands):
            raise ValueError("Stand not found")
        return deterministic(replace(state, stands=tuple(replace(s, charge=s.charge + event.get("amount"))
                                                        if s.instance_id == event.source_id else s for s in state.stands)))

    def _future_die(self, state, event):
        effect = ForcedDieEffect(event.get("face"), event.get("priority"), event.get("source"))
        return deterministic(replace(state, forced_die_effects=state.forced_die_effects + (effect,)))

    def run(self, state, events):
        if state.rule_version != self.registry.version:
            raise ValueError("State/rules version mismatch")
        pending = [(Fraction(1), state, tuple(events), ())]
        completed = []
        while pending:
            if self.cancel and self.cancel():
                from .errors import CalculationCancelled
                raise CalculationCancelled()
            probability, current, queue, trace = pending.pop()
            if not queue:
                completed.append(WeightedOutcome(probability, current, trace))
                continue
            if len(trace) >= self.max_events:
                raise RuntimeError("Event budget exceeded (possible activation cycle)")
            event, *tail = queue
            handler = self.handlers.get(event.type)
            # Lifecycle markers are logged; effect resolution is registered explicitly.
            if handler is None and event.type in {E.BUY_BUILDING, E.SELL_BUILDING, E.ADD_BUILDING, E.UNLOCK_LAND}:
                raise NotImplementedError(f"No action handler: {event.type}")
            outcomes = validate_distribution(handler(current, event) if handler else deterministic(current))
            for outcome in reversed(outcomes):
                transition = outcome.state
                entry = EventLogEntry(event, current, transition.state)
                pending.append((probability * outcome.probability, transition.state,
                                transition.followups + tuple(tail), trace + (entry,)))
        return validate_distribution(completed)

    @staticmethod
    def replay(initial, trace):
        state = initial
        for entry in trace:
            if entry.before != state:
                raise ValueError("Broken trace continuity")
            state = entry.after
        return state
