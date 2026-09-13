from dataclasses import replace

import pytest

from astral_town.model.enums import BuildingType as B, EventType as E, StandType as S, ActivationCause as C
from astral_town.model.events import Event
from astral_town.model.stand import StandInstance
from astral_town.rules.effects.luck import install_luck
from test_prosperity import setup,event
from test_promotion import template


def luck(kinds,assumptions=None,stands=()):
    state,engine,effects=setup(kinds,assumptions,stands)
    install_luck(effects)
    return state,engine,effects


def test_two_even_payout_and_natural_six_growth():
    state,engine,_=luck((B.FOUR_LEAF_INN,),{"four_leaf_growth_order":"after_payout"})
    result,=engine.run(state,(event(0,"die",2),event(0,"die",6)))
    assert result.state.wallet==24
    assert result.state.building(0).dice_coin_bonus==1


def test_forced_four_leaf_no_growth_and_sculpture_payout():
    state,engine,_=luck((B.FOUR_LEAF_INN,B.DICE_SCULPTURE))
    result,=engine.run(state,(event(0,"forced",cause=C.FORCED_DICE_EFFECT),event(1,"forced",cause=C.FORCED_DICE_EFFECT)))
    assert result.state.wallet==28
    assert result.state.building(0).dice_coin_bonus==0


@pytest.mark.parametrize("trigger",["die","forced"])
def test_pond_enables_two_dice(trigger):
    state,engine,_=luck((B.LUCKY_STAR_COIN_POND,))
    result,=engine.run(state,(event(0,trigger,1),))
    assert result.state.next_dice_count==2


def test_pond_and_hologram_two_dice_payout():
    state,engine,_=luck((B.LUCKY_STAR_COIN_POND,B.HOLOGRAM_EXPERIENCE_HUT))
    result,=engine.run(replace(state,last_roll=(4,6)),(event(0,"roll"),event(1,"roll"),event(1,"pass")))
    assert result.state.wallet==36
    assert result.state.next_dice_count==2


@pytest.mark.parametrize("trigger",["die","forced"])
def test_tower_absorbs_then_six_pays(trigger):
    state,engine,_=luck((B.DICE_TOWER,B.DICE_SCULPTURE),{"dice_tower_xp_transfer":"total"})
    state=state.with_building(replace(state.building(1),xp=3))
    result,=engine.run(state,(event(0,trigger,4),event(0,"die",6)))
    assert len(result.state.buildings)==1
    assert result.state.building(0).xp==3
    assert result.state.building(0).dice_coin_bonus==6
    assert result.state.wallet==34


def test_jasmine_threshold():
    state,engine,_=luck((),{"stand_charge_consumption":"subtract"},(StandInstance(10,S.JASMINE,3),))
    result,=engine.run(state,(Event(E.ACTIVATE_STAND,10,payload=(("trigger","roll"),)),))
    assert result.state.next_dice_count==2
    assert result.state.stands[0].charge==0


def test_shrimp_and_three_leaf_per_die():
    state,engine,_=luck((),{"stand_charge_consumption":"subtract","inventory_capacity":5,
                           "THREE_LEAF.distribution":[{"probability":"1","value":template(B.DICE_SCULPTURE)}]},
                         (StandInstance(10,S.FRIED_SHRIMP),StandInstance(11,S.THREE_LEAF,4)))
    events=(Event(E.ACTIVATE_STAND,10,payload=(("trigger","die"),("face",1))),)+tuple(
            Event(E.ACTIVATE_STAND,11,die_index=i,payload=(("trigger","die"),("face",6))) for i in range(2))
    result,=engine.run(state,events)
    assert result.state.forced_die_effects[0].face==6
    assert result.state.stands[1].charge==0
    assert result.state.inventory[0].building_type==B.DICE_SCULPTURE
