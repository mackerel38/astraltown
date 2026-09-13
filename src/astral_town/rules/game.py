"""Integration facade: full turn transitions with explicit unresolved inputs."""

from dataclasses import replace
from fractions import Fraction
from collections import OrderedDict

from astral_town.model.enums import ActivationCause as C, EventType as E, StandType, RuleConfidence
from astral_town.model.events import Event
from astral_town.model.outcomes import WeightedOutcome, validate_distribution
from .engine import EventEngine, Transition, deterministic
from .dice import dice_outcomes
from .effects.common import Effects
from .effects.prosperity import install_prosperity
from .effects.promotion import install_promotion
from .effects.luck import install_luck
from .effects.pirate import install_pirate
from .effects.neutral import install_neutral
from .management import install_management
from .movement import install_movement
from .randomness import configured_distribution


class Game:
    def __init__(self, registry, board, *, accept_topology_assumption=False):
        self.registry,self.board=registry,board
        if len(board.spaces)!=registry.require("board_size"):raise ValueError("Board size does not match selected rules")
        self.roll_cache=OrderedDict()
        self.roll_cache_hits=0
        self.roll_cache_limit=128
        self.topology_assumed=board.confidence not in {RuleConfidence.VERIFIED_CURRENT,RuleConfidence.COMMUNITY_CURRENT}
        self.engine=EventEngine(registry)
        install_management(self.engine)
        install_movement(self.engine,board,accept_topology_assumption=accept_topology_assumption)
        effects=self.effects=Effects(self.engine,board)
        for installer in (install_prosperity,install_promotion,install_luck,install_pirate,install_neutral):installer(effects)
        # All building pass effects now live in the effects registry.
        self.engine.handlers.pop(E.PASS_BUILDING)
        for et,trigger,bfilter in (
            (E.TURN_START,"turn_start",False),(E.AFTER_ROLL,"after",True),
            (E.ROLL_CONDITION,"roll",True),(E.DIE_FACE,"die",True),
            (E.PASS_BUILDING,"pass",True),(E.ON_STAY_BUILDING,"stay",True),
            (E.PASS_START,"start",False),(E.SHOP_REFRESH,"refresh",False),
            (E.LAND_SPECIAL_TILE,"special",False),
        ):
            effects.route(et,trigger,building_filter=lambda b, enabled=bfilter:enabled)
        self.engine.register(E.ROLL,self._roll)
        self.engine.register(E.MANAGEMENT_END,lambda s,e:deterministic(replace(s,phase="roll")))
        self.engine.register(E.TURN_END,self._turn_end)
        self.engine.register(E.STAGE_CLEAR,self._stage_clear)
        self.engine.register(E.ADVANCE_STAGE,self._advance)
        self.engine.register(E.STAND_SELECTION,self._stand_offers)
        self.engine.register(E.GAME_CLEAR,lambda s,e:deterministic(replace(s,status="cleared",phase="terminal")))
        self.engine.register(E.GAME_OVER,lambda s,e:deterministic(replace(s,status="failed",phase="terminal")))

    @property
    def exactness(self):
        value=self.registry.exactness
        return "assumption-based" if self.topology_assumed and value=="exact" else value

    def _roll(self,state,event):
        results=[]
        for outcome in dice_outcomes(state,self.registry):
            current=outcome.state
            order=self.registry.require("roll_effect_order")
            die_events=tuple(Event(E.DIE_FACE,cause=C.NATURAL_DIE,roll_id=current.roll_id,die_index=i,payload=(("face",face),)) for i,face in enumerate(current.last_roll))
            roll_event=(Event(E.ROLL_CONDITION,cause=C.NATURAL_DIE,roll_id=current.roll_id),)
            if order=="dice_then_roll":events=die_events+roll_event
            elif order=="roll_then_dice":events=roll_event+die_events
            else:raise ValueError("Invalid roll effect order")
            results.append(WeightedOutcome(outcome.probability,Transition(current,events+(Event(E.AFTER_ROLL,roll_id=current.roll_id),Event(E.MOVE_BEGIN,roll_id=current.roll_id)))))
        return validate_distribution(results)

    def _turn_end(self,state,event):
        if self.registry.require("stage_clear_timing")!="turn_end":raise ValueError("Only explicit turn_end stage timing is implemented")
        quotas=self.registry.require("stage_quotas")
        if not 0<=state.stage_index<len(quotas):raise ValueError("Stage index outside configured quotas")
        state=replace(state,turns_remaining=state.turns_remaining-1)
        if state.stage_progress>=quotas[state.stage_index]:return deterministic(state,Event(E.STAGE_CLEAR))
        if state.turns_remaining==0:return deterministic(state,Event(E.GAME_OVER))
        return deterministic(replace(state,phase="management"),Event(E.TURN_START),Event(E.MANAGEMENT_START))

    def _stage_clear(self,state,event):
        events=tuple(self.effects.event(b,"stage",event) for b in self.effects.placed(state))
        return deterministic(state,*events,Event(E.ADVANCE_STAGE))

    def _advance(self,state,event):
        points=self.registry.require("stage_progress_scores")[state.stage_index]
        state=replace(state,progress_score=state.progress_score+points)
        if state.stage_index+1==len(self.registry.require("stage_quotas")):
            return deterministic(state,Event(E.GAME_CLEAR))
        reset=self.registry.require("stage_progress_reset")
        if reset not in ("zero","carry"):raise ValueError("Invalid stage progress reset")
        next_stage=state.stage_index+1
        state=replace(state,stage_index=next_stage,stage_progress=0 if reset=="zero" else state.stage_progress,
                      turns_remaining=self.registry.require("stage_rolls")[next_stage],phase="stand_selection")
        return deterministic(state,Event(E.STAND_SELECTION))

    def _stand_offers(self,state,event):
        from .stand_catalog import stand_eligible
        results=[]
        for outcome in configured_distribution(self.registry,"stand_offers",state):
            offers=tuple(StandType(value) for value in outcome.state)
            if not offers or any(not stand_eligible(kind,state.selected_packs,self.registry) for kind in offers):raise ValueError("Impossible stand offer")
            results.append(WeightedOutcome(outcome.probability,Transition(replace(state,stand_offers=offers,phase="stand_selection"))))
        return validate_distribution(results)

    def roll(self,state):
        if self.engine.cancel and self.engine.cancel():
            from .errors import CalculationCancelled
            raise CalculationCancelled()
        if state.status!="playing" or state.phase not in {"management","roll"} or state.turns_remaining<=0:
            raise ValueError("State is not ready to roll")
        ids={s.id for s in self.board.spaces}
        lots={l.id for l in self.board.lots}
        if state.player_position not in ids or not state.unlocked_lots<=lots:raise ValueError("State does not fit board")
        key=(state,repr(self.registry.empirical),self.registry.legacy)
        if key in self.roll_cache:
            outcomes,dependencies=self.roll_cache.pop(key)
            self.roll_cache[key]=(outcomes,dependencies)
            self.registry.used.update(dependencies)
            self.roll_cache_hits+=1
            return outcomes
        previous=self.registry.used.copy()
        self.registry.used.clear()
        try:
            outcomes=self.engine.run(state,(Event(E.MANAGEMENT_END),Event(E.PRE_ROLL),Event(E.ROLL),Event(E.TURN_END)))
            dependencies=frozenset(self.registry.used)
        finally:self.registry.used.update(previous)
        if self.roll_cache_limit:
            self.roll_cache[key]=(outcomes,dependencies)
            while len(self.roll_cache)>self.roll_cache_limit:self.roll_cache.popitem(last=False)
        return outcomes

    def start_turn(self,state):
        if state.status!="playing" or state.phase!="management":raise ValueError("Not a management state")
        return self.engine.run(state,(Event(E.TURN_START),Event(E.MANAGEMENT_START)))
