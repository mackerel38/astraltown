from dataclasses import fields, replace
from fractions import Fraction

import pytest

from astral_town.model.building import BuildingInstance
from astral_town.model.enums import BuildingType as B, EventType as E, StandType as S
from astral_town.model.events import Event
from astral_town.model.stand import StandInstance
from astral_town.rules.effects.promotion import install_promotion, palunan_amount
from astral_town.rules.registry import RuleRegistry, UnresolvedRule
from test_prosperity import setup,event


def template(kind):
    b=BuildingInstance(0,kind)
    return {f.name:getattr(b,f.name) for f in fields(b) if f.name not in {"instance_id","location"}}


def promotion(kinds,assumptions=None,stands=()):
    state,engine,effects=setup(kinds,assumptions,stands)
    install_promotion(effects)
    return state,engine,effects


def test_piggy_and_piglet():
    state,engine,_=promotion((B.PIGGY_BANK,B.PIGLET_BANK))
    result,=engine.run(state,(event(0,"die",1),event(1,"after")))
    assert result.state.wallet==22
    assert [b.xp for b in result.state.buildings]==[2,1]


@pytest.mark.parametrize("level,bonus",[(1,1),(2,8),(3,25),(4,45)])
def test_piggy_sale(level,bonus):
    state,engine,_=promotion((B.PIGGY_BANK,),{"gain_progress_sources":["sale"]})
    state=state.with_building(replace(state.building(0),level=level))
    result,=engine.run(state,(Event(E.SELL_BUILDING,0),))
    assert result.state.wallet==20+4*level+bonus


def test_bookstore_current_xp_and_pass():
    state,engine,_=promotion((B.PIGGY_BANK,B.SMALL_BOOKSTORE,B.PIGLET_BANK),{"xp_max_storage":"discard"})
    state=state.with_building(replace(state.building(1),level=3))
    result,=engine.run(state,(event(1,"stay"),event(1,"pass")))
    assert result.state.building(0).level==2 and result.state.building(0).xp==1
    assert result.state.building(1).xp==6
    assert result.state.wallet==29


def test_two_vaults_observe_each_sale_and_gain_xp():
    state,engine,_=promotion((B.BECKONING_CAT_VAULT,B.PIGGY_BANK,B.PIGLET_BANK,B.BECKONING_CAT_VAULT),{"vault_xp_scope":"placed"})
    result,=engine.run(state,(event(0,"after"),Event(E.SELL_BUILDING,1),Event(E.SELL_BUILDING,2)))
    assert result.state.building(0).pass_coin_bonus==2
    assert result.state.building(3).pass_coin_bonus==2


@pytest.mark.parametrize("level,count,amount",[(1,1,1),(2,2,1),(3,2,2),(4,3,2)])
def test_fox_xp(level,count,amount):
    assumptions={"fox_self_target":False,"multi_target_sampling":"without_replacement","random_target_distribution":"uniform","xp_max_storage":"discard"}
    state,engine,_=promotion((B.FOX_ANTIQUE_SHOP,B.PIGGY_BANK,B.PIGLET_BANK,B.SMALL_WALLET),assumptions)
    state=state.with_building(replace(state.building(0),level=level))
    outcomes=engine.run(state,(event(0,"die",5),))
    assert sum(o.probability for o in outcomes)==1
    for o in outcomes:
        assert sum(b.xp for b in o.state.buildings[1:])==count*amount
        assert o.state.building(0).xp==(0 if level==4 else amount)


def test_fox_pass_exact_generation():
    distribution=[{"probability":"1/3","value":template(B.PIGGY_BANK)},{"probability":"2/3","value":template(B.PIGLET_BANK)}]
    state,engine,_=promotion((B.FOX_ANTIQUE_SHOP,),{"fox_generation_distribution":distribution,"inventory_capacity":5})
    outcomes=engine.run(state,(event(0,"pass"),))
    assert [o.probability for o in outcomes]==[Fraction(1,3),Fraction(2,3)]
    assert {o.state.inventory[0].building_type for o in outcomes}=={B.PIGGY_BANK,B.PIGLET_BANK}


def test_unknown_pig_threshold_and_palunan():
    state,engine,_=promotion((B.PIGGY_BANK,),stands=(StandInstance(10,S.PIG),))
    with pytest.raises(UnresolvedRule):engine.run(state,(Event(E.SELL_BUILDING,0),))
    with pytest.raises(UnresolvedRule):palunan_amount(8,RuleRegistry.builtin(),"palunan_sale")
    registry=RuleRegistry.builtin({"palunan_sale":"5/4","palunan_rounding":"floor"})
    assert palunan_amount(15,registry,"palunan_sale")==18
