from dataclasses import replace
from fractions import Fraction

from astral_town.model.enums import ActivationCause as C, EventType as E
from astral_town.model.events import ActivationKey, Event
from astral_town.model.outcomes import WeightedOutcome, validate_distribution
from astral_town.rules.engine import Transition, deterministic
from astral_town.rules.catalog import required_packs
from astral_town.rules.registry import UnresolvedRule


class Effects:
    """Dispatch activated objects independently of root event routing."""

    def __init__(self, engine, board):
        self.engine, self.registry, self.board = engine, engine.registry, board
        self.buildings, self.stands = {}, {}
        engine.register(E.ACTIVATE_BUILDING, self.activate_building)
        engine.register(E.ACTIVATE_STAND, self.activate_stand)

    def amount(self, building, name):
        return self.registry.require(f"{building.building_type.value}.{name}")[building.level - 1]

    def reward(self,state,key,allowed=None):
        from astral_town.rules.randomness import configured_distribution
        from astral_town.rules.economy import add_building
        from astral_town.rules.rewards import building_from_template,require_reward_capacity
        require_reward_capacity(state,self.registry)
        rows=configured_distribution(self.registry,key,state)
        results=[]
        for row in rows:
            b=building_from_template(state,row.state,self.registry)
            if allowed is not None and b.building_type not in allowed:raise ValueError("Impossible reward type")
            results.append(WeightedOutcome(row.probability,Transition(add_building(state,b,self.registry))))
        return validate_distribution(results)

    def placed(self, state, *, pack=None, kind=None, exclude=None):
        return tuple(b for b in sorted(state.buildings, key=lambda b: b.location)
                     if b.instance_id != exclude and (kind is None or b.building_type in kind)
                     and (pack is None or pack in required_packs(b.building_type, self.registry)))

    def adjacent(self, state, building, *, pack=None, kind=None):
        lot = next(lot for lot in self.board.lots if lot.id == building.location)
        return tuple(b for b in self.placed(state, pack=pack, kind=kind) if b.location in lot.adjacent_lots)

    def event(self, building, trigger, parent, *, cause=None):
        return Event(E.ACTIVATE_BUILDING, building.instance_id, cause or parent.cause, parent.roll_id,
                     parent.die_index, (("trigger", trigger), ("face", parent.get("face"))), parent.chain)

    def gain(self, state, amount, parent, *, source="building"):
        return deterministic(state, replace(parent, type=E.GAIN_COIN,
            payload=(("amount", amount), ("progress", source in self.registry.require("gain_progress_sources")))))

    def bonus(self, state, targets, field, amount):
        for building in targets:
            current = state.building(building.instance_id)
            state = state.with_building(replace(current, **{field: getattr(current, field) + amount}))
        return state

    def random_target(self, state, targets, key, apply):
        if not targets:
            # Empty-target behavior is an independent unresolved rule.
            if self.registry.require("empty_random_target") != "no_effect":
                raise ValueError("Unsupported empty target behavior")
            return deterministic(state)
        if len(targets) == 1:
            return apply(state, targets[0])
        distribution = self.registry.distribution(key,state)
        if isinstance(distribution,tuple):
            mapping={str(row["value"]):row["probability"] for row in distribution}
            if len(mapping)!=len(distribution) or set(mapping)!={str(b.location) for b in targets}:
                raise ValueError("Target distribution must cover exactly eligible locations")
            distribution=mapping
        if distribution == "uniform":
            probabilities = (Fraction(1, len(targets)),) * len(targets)
        else:
            probabilities = tuple(Fraction(distribution[str(b.location)]) for b in targets)
        outcomes = []
        for target, probability in zip(targets, probabilities):
            if probability == 0:
                continue
            for result in apply(state, target):
                outcomes.append(replace(result, probability=probability * result.probability))
        return validate_distribution(outcomes)

    def activate_building(self, state, event):
        try:
            building = state.building(event.source_id)
        except StopIteration:
            return deterministic(state)  # Earlier explicitly ordered effect removed it.
        trigger = event.get("trigger")
        key = ActivationKey(event.roll_id, building.instance_id, trigger)
        if key in event.chain:
            return deterministic(state)
        event = replace(event, chain=event.chain + (key,))
        handler = self.buildings.get(building.building_type)
        if handler is None:
            raise NotImplementedError(f"Building effect not installed: {building.building_type}")
        return handler(state, building, trigger, event)

    def activate_stand(self, state, event):
        stand = next(s for s in state.stands if s.instance_id == event.source_id)
        handler = self.stands.get(stand.stand_type)
        if handler is None:
            raise NotImplementedError(f"Stand effect not installed: {stand.stand_type}")
        return handler(state, stand, event.get("trigger"), event)

    def listens(self,obj,trigger,state,event):
        name=(obj.building_type if hasattr(obj,"building_type") else obj.stand_type).value
        # Pig's disputed sale rule is handled only by the explicit sale observer.
        if name=="PIG":return trigger=="sale"
        if trigger not in self.registry.require(name+".triggers"):return False
        if trigger!="die":return True
        face=event.get("face")
        if face not in self.registry.require(name+".natural_faces"):return False
        if name=="LUCKY_COLOR_GATE" and {1,6}<=set(state.last_roll):
            policy=self.registry.require("LUCKY_COLOR_GATE.different_face_branches")
            if policy=="first":return event.die_index==0
            if policy!="both":raise ValueError("Invalid Gate two-branch assumption")
        matching=tuple(i for i,v in enumerate(state.last_roll) if v==face)
        if len(matching)>1:
            cardinality=self.registry.require(name+".natural_cardinality")
            if cardinality=="PER_ROLL":return event.die_index==matching[0]
            if cardinality!="PER_DIE":raise ValueError("Invalid declared trigger cardinality")
        return True

    def route(self, event_type, trigger, *, building_filter=lambda b: True, stand_filter=lambda s: True):
        previous = self.engine.handlers.get(event_type)

        def handler(state, event):
            if event.source_id is not None and event_type in {E.PASS_BUILDING,E.ON_STAY_BUILDING}:
                candidate=state.building(event.source_id)
                targets = (candidate,) if self.listens(candidate,trigger,state,event) else ()
            else:
                targets = tuple(b for b in self.placed(state) if building_filter(b) and self.listens(b,trigger,state,event))
            events = [self.event(b, trigger, event) for b in targets]
            events += [Event(E.ACTIVATE_STAND, s.instance_id, event.cause, event.roll_id, event.die_index,
                              (("trigger", trigger), ("face", event.get("face")), ("building_id", event.source_id)), event.chain)
                       for s in sorted(state.stands,key=lambda s:s.stand_type) if stand_filter(s) and self.listens(s,trigger,state,event)]
            if len(events)>1:
                policy = self.registry.require("simultaneous_event_order")
                if policy != "board_then_stands":
                    raise ValueError("Supported explicit order: board_then_stands")
            base = previous(state,event) if previous else deterministic(state)
            return tuple(WeightedOutcome(o.probability, Transition(o.state.state, tuple(events) + o.state.followups)) for o in base)

        self.engine.handlers[event_type] = handler
