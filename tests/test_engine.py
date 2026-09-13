from dataclasses import replace

import pytest

from astral_town.model.building import BuildingInstance, ShopOffer
from astral_town.model.enums import BuildingType as B, EventType as E, Pack, StandType
from astral_town.model.events import Event
from astral_town.model.stand import StandInstance
from astral_town.rules.catalog import eligible
from astral_town.rules.economy import gain_xp, merge_buildings, place_building
from astral_town.rules.engine import EventEngine
from astral_town.rules.management import install_management
from astral_town.rules.registry import RuleRegistry, UnresolvedRule
from astral_town.samples import model_sample


def registry():
    return RuleRegistry.builtin({"inventory_capacity": 5, "shop_refill": "none", "xp_max_storage": "discard", "gain_progress_sources": ["sale"]})


def test_gain_spend_and_replay():
    state = model_sample()
    engine = EventEngine(registry())
    events = (Event(E.GAIN_COIN, payload=(("amount", 10), ("progress", True))), Event(E.SPEND_COIN, payload=(("amount", 8),)))
    result, = engine.run(state, events)
    assert (result.state.wallet, result.state.stage_progress) == (22, 10)
    assert tuple(x.event for x in result.events) == events
    assert engine.replay(state, result.events) == result.state
    assert engine.run(state, events) == (result,)
    assert state.wallet == 20


@pytest.mark.parametrize("amount,level,xp", [(4,1,4),(5,2,0),(14,2,9),(15,3,0),(29,3,14),(30,4,0),(100,4,0)])
def test_xp(amount, level, xp):
    b = gain_xp(model_sample().buildings[0], amount, registry())
    assert (b.level,b.xp) == (level,xp)


def test_unknown_max_xp_storage():
    with pytest.raises(UnresolvedRule):
        gain_xp(model_sample().buildings[0], 31, RuleRegistry.builtin())


def test_buy_does_not_reduce_progress():
    state = replace(model_sample(), stage_progress=15, shop_offers=(ShopOffer(0, BuildingInstance(8,B.SMALL_WALLET),8),))
    engine = EventEngine(registry())
    install_management(engine)
    result, = engine.run(state, (Event(E.BUY_BUILDING, payload=(("offer_id",0),)),))
    assert result.state.wallet == 12
    assert result.state.stage_progress == 15
    assert result.state.inventory[-1].instance_id == 8
    assert not result.state.shop_offers


def test_unknown_refill_blocks_buy():
    state=replace(model_sample(),shop_offers=(ShopOffer(0,BuildingInstance(8,B.SMALL_WALLET),8),))
    engine=EventEngine(RuleRegistry.builtin())
    install_management(engine)
    with pytest.raises(UnresolvedRule) as exc:
        engine.run(state,(Event(E.BUY_BUILDING,payload=(("offer_id",0),)),))
    assert exc.value.rule_ids == ("shop_refill",)


def test_place_move_unplace_and_capacity():
    state = place_building(model_sample(), 2, 1, registry())
    assert not state.inventory
    state = place_building(state, 1, None, registry())
    state = place_building(state, 2, 0, registry())
    assert state.building(2).location == 0
    with pytest.raises(ValueError):
        place_building(state, 1, 0, registry())


def test_merge_treasure_retains_target_decay_and_unknown_xp():
    state=replace(model_sample(),buildings=(BuildingInstance(1,B.TREASURE,location=0),),inventory=(BuildingInstance(2,B.TREASURE,treasure_decay=5),))
    result=merge_buildings(state,1,2,registry())
    assert result.building(1).level == 2
    assert result.building(1).treasure_decay == 0
    with pytest.raises(UnresolvedRule):
        merge_buildings(state.with_building(replace(state.building(2),xp=1)),1,2,registry())
    with pytest.raises(ValueError):
        merge_buildings(state.with_building(replace(state.building(2),level=4)),1,2,registry())


@pytest.mark.parametrize("kind,packs", [(B.LUCKY_COLOR_GATE,{Pack.PROSPERITY,Pack.LUCK}), (B.RUDDER,{Pack.LUCK,Pack.PIRATE})])
def test_hybrid_eligibility(kind,packs):
    assert eligible(kind,frozenset(packs),registry())
    for pack in packs:
        assert not eligible(kind,frozenset({pack}),registry())


def test_bonus_charge_and_future_die():
    state=replace(model_sample(),stands=(StandInstance(1,StandType.SHOVEL),))
    engine=EventEngine(registry())
    result,=engine.run(state,(Event(E.BONUS,1,payload=(("field","pass_coin_bonus"),("amount",4))),
                              Event(E.STAND_CHARGE,1,payload=(("amount",1),)),
                              Event(E.SET_FUTURE_DIE,payload=(("face",4),("priority",2),("source","ANCHOR"))),
                              Event(E.FORCED_STOP)))
    assert result.state.building(1).pass_coin_bonus == 4
    assert result.state.building(1).dice_coin_bonus == 0
    assert result.state.stands[0].charge == 1
    assert result.state.forced_die_effects[0].face == 4
    assert result.state.forced_stop


def test_sell_bonus():
    engine=EventEngine(registry())
    install_management(engine)
    state=model_sample()
    result,=engine.run(state,(Event(E.SELL_BUILDING,2),))
    assert result.state.wallet == 25
    assert not result.state.inventory
