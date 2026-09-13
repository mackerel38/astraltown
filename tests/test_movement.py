from dataclasses import replace
from fractions import Fraction
from random import Random

import pytest

from astral_town.model.board import Board, Space
from astral_town.model.enums import BuildingType as B, EventType as E, RuleConfidence as C, SpaceType as S, TriggerCardinality as T
from astral_town.model.events import Event
from astral_town.model.state import ForcedDieEffect
from astral_town.rules.dice import dice_outcomes, trigger_events
from astral_town.rules.engine import EventEngine
from astral_town.rules.movement import install_movement
from astral_town.rules.randomness import sample
from astral_town.rules.registry import RuleRegistry, UnresolvedRule
from astral_town.samples import model_sample


def board():
    from astral_town.model.board import Lot
    return Board(tuple(Space(i, S.START if i==0 else S.COIN if i==4 else S.NORMAL, 0 if i==2 else None) for i in range(16)),
                 (Lot(0,frozenset()),),C.INFERRED,"Artificial movement fixture")


def engine(assumptions=None):
    rules={"shop_distribution":[{"probability":"1","value":[]}],"gain_progress_sources":["building","tile"]}
    rules.update(assumptions or {})
    engine=EventEngine(RuleRegistry.builtin(rules))
    install_movement(engine,board(),accept_topology_assumption=True)
    return engine


@pytest.mark.parametrize("count,size",[(1,6),(2,36)])
def test_dice_exact(count,size):
    outcomes=dice_outcomes(replace(model_sample(),next_dice_count=count),RuleRegistry.builtin())
    assert len(outcomes)==size
    assert sum(o.probability for o in outcomes)==1
    assert all(o.probability==Fraction(1,size) for o in outcomes)
    assert len({o.state.last_roll for o in outcomes})==size


def test_two_dice_triggers():
    state=replace(model_sample(),last_roll=(4,6))
    assert [e.die_index for e in trigger_events(state,1,{2,4,6},T.PER_DIE)]==[0,1]
    state=replace(state,last_roll=(3,4))
    assert len(trigger_events(state,1,{3,4},T.PER_ROLL))==1


def test_forced_priority_and_consumption():
    state=replace(model_sample(),next_dice_count=2,forced_die_effects=(ForcedDieEffect(6,1,"FRIED_SHRIMP"),ForcedDieEffect(4,2,"ANCHOR")))
    with pytest.raises(UnresolvedRule):
        dice_outcomes(state,RuleRegistry.builtin())
    outcomes=dice_outcomes(state,RuleRegistry.builtin({"forced_die_consumption":"winner","forced_die_index":0}))
    assert len(outcomes)==6
    assert {o.state.last_roll[0] for o in outcomes}=={4}
    assert {o.state.last_roll[1] for o in outcomes}==set(range(1,7))
    assert all(o.state.forced_die_effects==(state.forced_die_effects[0],) for o in outcomes)


def test_intermediate_spaces_and_coin_tile():
    outcome,=engine().run(model_sample(),(Event(E.MOVE_BEGIN,payload=(("steps",4),)),))
    visited=[e.after.player_position for e in outcome.events if e.before.player_position!=e.after.player_position]
    assert visited==[1,2,3,4]
    assert E.PASS_BUILDING in [e.event.type for e in outcome.events]
    assert outcome.state.wallet==25


def test_start_discards_remaining_and_opens_shop():
    state=replace(model_sample(),player_position=14)
    result,=engine().run(state,(Event(E.MOVE_BEGIN,payload=(("steps",6),)),))
    assert result.state.player_position==0
    assert result.state.movement_remaining==0
    assert result.state.forced_stop
    assert result.state.shop_refresh_count==1
    types=[e.event.type for e in result.events]
    assert types.index(E.PASS_START)<types.index(E.FORCED_STOP)<types.index(E.SHOP_REFRESH)


def test_anchor_discards_remaining():
    state=model_sample().with_building(replace(model_sample().buildings[0],building_type=B.ANCHOR))
    result,=engine().run(state,(Event(E.MOVE_BEGIN,payload=(("steps",6),)),))
    assert result.state.player_position==2
    assert result.state.movement_remaining==0
    assert result.state.forced_stop
    assert result.state.wallet==24
    assert result.state.forced_die_effects[0].face==4


def test_unknown_board_not_assumed():
    with pytest.raises(UnresolvedRule):
        install_movement(EventEngine(RuleRegistry.builtin()),board())


def test_unknown_card_and_shop():
    e=engine()
    with pytest.raises(UnresolvedRule) as exc:
        e.run(model_sample(),(Event(E.LAND_SPECIAL_TILE,payload=(("tile","CARD"),)),))
    assert exc.value.rule_ids==("card_distribution",)
    e=EventEngine(RuleRegistry.builtin())
    install_movement(e,board(),accept_topology_assumption=True)
    with pytest.raises(UnresolvedRule):
        e.run(replace(model_sample(),player_position=15),(Event(E.MOVE_BEGIN,payload=(("steps",1),)),))


def test_sampling_reproducible():
    outcomes=dice_outcomes(model_sample(),RuleRegistry.builtin())
    a,b=Random(123),Random(123)
    assert [sample(outcomes,a).state.last_roll for _ in range(100)]==[sample(outcomes,b).state.last_roll for _ in range(100)]
