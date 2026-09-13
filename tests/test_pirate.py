from dataclasses import replace

import pytest

from astral_town.model.enums import BuildingType as B, EventType as E, StandType as S, ActivationCause as C
from astral_town.model.events import Event
from astral_town.model.stand import StandInstance
from astral_town.rules.effects.pirate import install_pirate
from astral_town.rules.effects.luck import install_luck
from test_prosperity import setup,event
from test_promotion import template


def pirate(kinds,assumptions=None,stands=()):
    config={"treasure_minimum":0,"stand_charge_consumption":"subtract"}
    config.update(assumptions or {})
    state,engine,effects=setup(kinds,config,stands)
    install_pirate(effects)
    install_luck(effects)
    return state,engine,effects


def test_treasure_every_activation_decays_and_charges_shovel():
    state,engine,_=pirate((B.TREASURE,),stands=(StandInstance(10,S.SHOVEL,6),))
    result,=engine.run(state,(event(0,"stay",cause=C.NATURAL_STAY),event(0,"stay",cause=C.TRIGGERED_STAY)))
    assert result.state.wallet==20+12+11+88
    assert result.state.building(0).treasure_decay==2
    assert result.state.stands[0].charge==0


def test_treasure_minimum_configured():
    state,engine,_=pirate((B.TREASURE,),{"treasure_minimum":2})
    state=state.with_building(replace(state.building(0),treasure_decay=99))
    result,=engine.run(state,(event(0,"stay"),))
    assert result.state.wallet==22


def test_sail_three_triggers():
    state,engine,_=pirate((B.SAIL,))
    result,=engine.run(state,(event(0,"pass"),event(0,"stay"),event(0,"die",4)))
    assert result.state.wallet==30


def test_rudder_triggers_treasure_and_luck_forced():
    state,engine,_=pirate((B.RUDDER,B.TREASURE,B.FOUR_LEAF_INN))
    result,=engine.run(state,(event(0,"pass"),event(0,"stay")))
    assert result.state.wallet==20+12+6+2
    assert result.state.building(1).treasure_decay==1
    assert result.state.building(2).dice_coin_bonus==0


def test_cannon_adjacent_stays_and_reward():
    state,engine,_=pirate((B.TREASURE,B.CANNON,B.SAIL,B.TREASURE),{"inventory_capacity":5,"cannon_reward_distribution":[{"probability":"1","value":template(B.TREASURE)}]})
    result,=engine.run(state,(event(1,"die",4),event(1,"pass")))
    assert result.state.wallet==40
    assert result.state.building(0).treasure_decay==1
    assert result.state.building(3).treasure_decay==0
    assert result.state.inventory[0].building_type==B.TREASURE


def test_captain_all_stays_before_any_removal():
    state,engine,_=pirate((B.CAPTAIN_HAT,B.TREASURE,B.TREASURE),stands=(StandInstance(10,S.SHOVEL,7),))
    result,=engine.run(state,(event(0,"stay"),event(0,"pass")))
    assert result.state.wallet==20+24+88+8+24
    assert len(result.state.buildings)==1
    assert result.state.building(0).captain_pass_bonus==24
    indices=[i for i,e in enumerate(result.events) if e.event.type==E.ACTIVATE_BUILDING and e.event.source_id in (1,2)]
    removals=[i for i,e in enumerate(result.events) if e.event.type==E.REMOVE_BUILDING]
    assert max(indices)<min(removals)
    assert result.events[removals[0]].before.building(1).treasure_decay==1
    assert result.events[removals[0]].before.building(2).treasure_decay==1


def test_pirate_king_only_pass_stay_small_shark_count():
    state,engine,_=pirate((B.SAIL,B.RUDDER,B.SMALL_WALLET),stands=(StandInstance(10,S.PIRATE_KING),StandInstance(11,S.SMALL_SHARK)))
    result,=engine.run(state,tuple(Event(E.ACTIVATE_STAND,i,payload=(("trigger","start"),)) for i in (10,11)))
    assert result.state.wallet==22
    assert result.state.building(0).pass_coin_bonus==4
    assert result.state.building(1).stay_coin_bonus==4
    assert all(b.dice_coin_bonus==0 for b in result.state.buildings)
    assert result.state.building(2).stay_coin_bonus==0


def test_great_shark_threshold_all_treasure_sail():
    state,engine,_=pirate((B.TREASURE,B.SAIL),stands=(StandInstance(10,S.GREAT_SHARK,3),StandInstance(11,S.SHOVEL)))
    result,=engine.run(state,(Event(E.ACTIVATE_STAND,10,payload=(("trigger","die"),("face",4))),))
    assert result.state.wallet==36
    assert result.state.stands[0].charge==0
    assert result.state.stands[1].charge==1
