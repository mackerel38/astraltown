"""Bounded BFS over management sequences, with canonical deduplication."""

from collections import deque
from dataclasses import dataclass, replace
from fractions import Fraction

from astral_town.model.enums import EventType as E
from astral_town.model.events import Event
from astral_town.model.outcomes import WeightedOutcome
from astral_town.model.stand import StandInstance
from astral_town.rules.registry import UnresolvedRule
from astral_town.rules.engine import EventEngine
from astral_town.rules.errors import IllegalAction


@dataclass(frozen=True)
class Action:
    kind: str
    source_id: int | None = None
    target: int | None = None

    def describe(self):
        return f"{self.kind}({self.source_id}, {self.target})"


@dataclass(frozen=True)
class ManagementPlan:
    actions: tuple[Action,...]
    state: object


@dataclass(frozen=True)
class ManagementCandidates:
    plans: tuple[ManagementPlan,...]
    truncated: bool
    unresolved: tuple[str,...]
    visited: int


def actions(game,state):
    if state.phase=="stand_selection":
        return tuple(Action("SELECT_STAND",target=i) for i in range(len(state.stand_offers)))
    result=[Action("END_MANAGEMENT_AND_ROLL")]
    for offer in state.shop_offers:
        result.append(Action("BUY",target=offer.offer_id))
    owned=state.buildings+state.inventory
    for building in owned:
        result.append(Action("SELL",building.instance_id))
        occupied={b.location for b in state.buildings if b.instance_id!=building.instance_id}
        for lot in sorted(state.unlocked_lots-occupied):
            if lot!=building.location:result.append(Action("PLACE" if building.location is None else "MOVE_BUILDING",building.instance_id,lot))
        if building.location is not None:result.append(Action("UNPLACE",building.instance_id))
        for target in owned:
            if target.instance_id!=building.instance_id and target.building_type==building.building_type and building.level<4:
                result.append(Action("MERGE",target.instance_id,building.instance_id))
    for lot in game.board.lots:
        if lot.id not in state.unlocked_lots:result.append(Action("UNLOCK_LAND",target=lot.id))
    result.append(Action("REFRESH_SHOP"))
    return tuple(result)


def apply_action(game,state,action):
    if action.kind=="END_MANAGEMENT_AND_ROLL":return (WeightedOutcome(Fraction(1),replace(state,phase="roll")),)
    if action.kind=="SELECT_STAND":
        if state.phase!="stand_selection":raise ValueError("Not selecting stand")
        kind=state.stand_offers[action.target]
        if any(s.stand_type==kind for s in state.stands):
            if game.registry.require("stand_selection_duplicates")!="allow":raise ValueError("Duplicate stand rejected")
        sid=max((s.instance_id for s in state.stands),default=-1)+1
        new=replace(state,stands=state.stands+(StandInstance(sid,kind),),stand_offers=(),phase="management")
        return game.start_turn(new)
    mapping={"BUY":E.BUY_BUILDING,"SELL":E.SELL_BUILDING,"MERGE":E.MERGE_BUILDING,"PLACE":E.PLACE_BUILDING,
             "MOVE_BUILDING":E.MOVE_BUILDING,"UNPLACE":E.PLACE_BUILDING,"UNLOCK_LAND":E.UNLOCK_LAND,"REFRESH_SHOP":E.SHOP_REFRESH}
    payload=()
    if action.kind=="BUY":payload=(("offer_id",action.target),)
    elif action.kind=="MERGE":payload=(("material",action.target),)
    elif action.kind in {"PLACE","MOVE_BUILDING","UNPLACE"}:payload=(("location",action.target),)
    elif action.kind=="UNLOCK_LAND":payload=(("lot",action.target),)
    elif action.kind=="REFRESH_SHOP":
        from astral_town.rules.economy import spend_coin
        prices=game.registry.require("refresh_prices")
        if state.shop_refresh_count>=len(prices):raise UnresolvedRule("refresh_price_next")
        state=spend_coin(state,prices[state.shop_refresh_count])
        payload=(("reason","manual"),)
    return game.engine.run(state,(Event(mapping[action.kind],action.source_id,payload=payload),))


def enumerate_plans(game,state,*,max_actions=2,max_states=2000):
    if max_actions<0 or max_states<1:raise ValueError("Invalid management budget")
    queue=deque([(state,())])
    visited={state.canonical_key()}
    plans=[]
    missing=set()
    truncated=False
    while queue:
        current,path=queue.popleft()
        if current.phase!="stand_selection":plans.append(ManagementPlan(path+(Action("END_MANAGEMENT_AND_ROLL"),),replace(current,phase="roll")))
        available=tuple(a for a in actions(game,current) if a.kind!="END_MANAGEMENT_AND_ROLL")
        if len(path)>=max_actions:
            truncated |= bool(available)
            continue
        for action in available:
            try:outcomes=apply_action(game,current,action)
            except UnresolvedRule as exc:
                missing.update(exc.rule_ids)
                continue
            except IllegalAction:continue
            if len(outcomes)!=1:
                # A contingent management decision cannot be flattened into a fixed plan.
                missing.add("stochastic_management_search")
                continue
            result=outcomes[0].state
            key=result.canonical_key()
            if key in visited:continue
            if len(visited)>=max_states:
                truncated=True
                continue
            visited.add(key)
            queue.append((result,path+(action,)))
    return ManagementCandidates(tuple(plans),truncated,tuple(sorted(missing)),len(visited))


def wallet_dominates(left,right):
    """Opt-in helper, only safe when future actions/evaluation are wallet-monotone."""
    return left.wallet>=right.wallet and replace(left,wallet=right.wallet).canonical_key()==right.canonical_key()
