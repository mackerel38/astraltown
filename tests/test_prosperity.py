from dataclasses import replace
from fractions import Fraction

import pytest

from astral_town.model.board import Board, Lot, Space
from astral_town.model.building import BuildingInstance
from astral_town.model.enums import ActivationCause as C, BuildingType as B, EventType as E, RuleConfidence as RC, SpaceType, StandType as S
from astral_town.model.events import Event
from astral_town.model.stand import StandInstance
from astral_town.rules.engine import EventEngine
from astral_town.rules.effects.common import Effects
from astral_town.rules.effects.prosperity import install_prosperity
from astral_town.rules.movement import install_movement
from astral_town.rules.registry import RuleRegistry, UnresolvedRule
from astral_town.samples import model_sample


def setup(kinds, assumptions=None, stands=()):
    state=replace(model_sample(),unlocked_lots=frozenset(range(len(kinds))),inventory=(),
                  buildings=tuple(BuildingInstance(i,k,location=i) for i,k in enumerate(kinds)),stands=stands)
    board=Board(tuple(Space(i,SpaceType.START if i==0 else SpaceType.NORMAL, i-1 if 1<=i<=len(kinds) else None) for i in range(16)),
                tuple(Lot(i,frozenset(j for j in range(len(kinds)) if abs(i-j)==1)) for i in range(len(kinds))),RC.INFERRED,"artificial")
    config={"gain_progress_sources":["building","stand"],"simultaneous_event_order":"board_then_stands"}
    config.update(assumptions or {})
    engine=EventEngine(RuleRegistry.builtin(config))
    effects=Effects(engine,board)
    install_prosperity(effects)
    return state,engine,effects


def event(instance_id,trigger,face=None,cause=None):
    return Event(E.ACTIVATE_BUILDING,instance_id,cause,1,payload=(("trigger",trigger),("face",face)))


def test_wallet_and_well_stage():
    state,engine,_=setup((B.SMALL_WALLET,B.WISHING_WELL))
    result,=engine.run(state,(event(0,"after"),event(1,"stage"),event(1,"after")))
    assert result.state.wallet==23
    assert result.state.building(1).wish_stage_bonus==1


def test_money_tree_only_adjacent_prosperity():
    state,engine,_=setup((B.SMALL_WALLET,B.MONEY_TREE,B.LUCKY_COLOR_GATE,B.WISHING_WELL))
    result,=engine.run(state,(event(1,"stay"),))
    assert [b.dice_coin_bonus for b in result.state.buildings]==[2,0,2,0]


def test_gate_count_side_and_external_bonus():
    state,engine,_=setup((B.LUCKY_COLOR_GATE,B.SMALL_WALLET))
    state=state.with_building(replace(state.building(0),dice_coin_bonus=3))
    a,=engine.run(state,(event(0,"die",6),))
    b,=engine.run(state,(event(0,"forced",cause=C.FORCED_DICE_EFFECT),))
    assert a.state.wallet==25
    assert b.state.wallet==27


def test_hall_once_and_repeated_independent_chains():
    state,engine,effects=setup((B.HALL_OF_WEALTH,B.SMALL_WALLET,B.HALL_OF_WEALTH),{"forced_SMALL_WALLET":"after"})
    effects.route(E.ROLL_CONDITION,"roll")
    state=replace(state,last_roll=(3,4))
    result,=engine.run(state,(Event(E.ROLL_CONDITION,roll_id=1),))
    assert result.state.wallet==22
    forced=[e for e in result.events if e.event.type==E.ACTIVATE_BUILDING and e.event.cause==C.FORCED_DICE_EFFECT]
    assert len(forced)==2


def test_hall_chain_guard_with_explicit_forced_assumption():
    state,engine,_=setup((B.HALL_OF_WEALTH,B.HALL_OF_WEALTH,B.SMALL_WALLET),
                        {"forced_HALL_OF_WEALTH":"activate_neighbors","forced_SMALL_WALLET":"after"})
    result,=engine.run(replace(state,last_roll=(3,)),(event(0,"roll"),))
    assert result.state.wallet==21
    assert len(result.events)<20


def test_unverified_forced_behavior_is_not_invented():
    state,engine,_=setup((B.HALL_OF_WEALTH,B.SMALL_WALLET))
    with pytest.raises(UnresolvedRule) as exc:
        engine.run(replace(state,last_roll=(3,)),(event(0,"roll"),))
    assert exc.value.rule_ids==("forced_SMALL_WALLET",)


def test_rabbit_payout_and_exclusion():
    state,engine,_=setup((B.RABBIT_INN,B.SMALL_WALLET,B.WISHING_WELL),{"random_target_distribution":"uniform"})
    results=engine.run(state,(event(0,"pass"),))
    assert len(results)==2
    assert all(r.probability==Fraction(1,2) for r in results)
    assert all(r.state.wallet==26 and r.state.building(0).dice_coin_bonus==0 for r in results)
    assert all(sum(b.dice_coin_bonus for b in r.state.buildings)==1 for r in results)


def test_unknown_random_target_blocks():
    state,engine,_=setup((B.RABBIT_INN,B.SMALL_WALLET,B.WISHING_WELL))
    with pytest.raises(UnresolvedRule):
        engine.run(state,(event(0,"pass"),))


def test_rabbit_solo_still_pays_when_empty_strengthening_is_explicitly_noop():
    state,engine,_=setup((B.RABBIT_INN,),{"empty_random_target":"no_effect"})
    result,=engine.run(state,(event(0,"pass"),))
    assert result.state.wallet==26


@pytest.mark.parametrize("kind,trigger",[(S.MIMI,"after"),(S.RABBIT,"start")])
def test_strength_stands(kind,trigger):
    state,engine,_=setup((B.SMALL_WALLET,),stands=(StandInstance(10,kind),))
    result,=engine.run(state,(Event(E.ACTIVATE_STAND,10,payload=(("trigger",trigger),)),))
    assert result.state.building(0).dice_coin_bonus==1


def test_raccoon():
    state,engine,_=setup((B.SMALL_WALLET,),stands=(StandInstance(10,S.RACCOON),))
    result,=engine.run(state,(Event(E.ACTIVATE_STAND,10,payload=(("trigger","pass"),("building_id",0))),))
    assert result.state.wallet==21


def test_start_shop_charges_update():
    state,engine,effects=setup((B.SMALL_WALLET,),{"shop_distribution":[{"probability":"1","value":[]}]},stands=(StandInstance(10,S.UPDATE),))
    install_movement(engine,effects.board,accept_topology_assumption=True)
    effects.route(E.SHOP_REFRESH,"refresh",building_filter=lambda b:False)
    result,=engine.run(replace(state,player_position=15),(Event(E.MOVE_BEGIN,payload=(("steps",4),)),))
    assert result.state.stands[0].charge==1


def test_update_threshold():
    state,engine,_=setup((B.SMALL_WALLET,),{"stand_charge_consumption":"subtract"},stands=(StandInstance(10,S.UPDATE,2),))
    result,=engine.run(state,(Event(E.ACTIVATE_STAND,10,payload=(("trigger","refresh"),)),))
    assert result.state.stands[0].charge==0
    assert result.state.building(0).dice_coin_bonus==1
