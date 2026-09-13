from dataclasses import replace
from fractions import Fraction

import pytest

from astral_town.model.building import BuildingInstance,ShopOffer
from astral_town.model.enums import BuildingType as B,EventType as E,Pack
from astral_town.model.events import Event
from astral_town.rules.registry import UnresolvedRule
from astral_town.rules.randomness import configured_distribution
from astral_town.solver.management_search import Action,apply_action
from test_game import game_fixture
from test_promotion import template


def test_shop_refill_is_exact_chance_node():
    distribution=[{"probability":"1/4","value":{"building":template(B.SMALL_WALLET),"price":8}},
                  {"probability":"3/4","value":{"building":template(B.PIGGY_BANK),"price":8}}]
    game,state=game_fixture({"shop_refill":"replace_slot","shop_refill_distribution":distribution,"purchase_refill_counts_as_refresh":False})
    state=replace(state,shop_offers=(ShopOffer(10,BuildingInstance(9,B.SMALL_WALLET),8),))
    outcomes=apply_action(game,state,Action("BUY",target=10))
    assert [o.probability for o in outcomes]==[Fraction(1,4),Fraction(3,4)]
    assert all(o.state.wallet==12 and o.state.stage_progress==0 for o in outcomes)
    assert all(o.state.shop_offers[0].offer_id==10 for o in outcomes)


def test_ineligible_card_reward_rejected():
    game,state=game_fixture({"card_distribution":[{"probability":"1","value":template(B.LUCKY_COLOR_GATE)}]})
    state=replace(state,selected_packs=frozenset({Pack.PROSPERITY}))
    with pytest.raises(ValueError):game.engine.run(state,(Event(E.LAND_SPECIAL_TILE,payload=(("tile","CARD"),)),))


def test_reward_overflow_remains_unresolved():
    game,state=game_fixture({"inventory_capacity":0})
    with pytest.raises(UnresolvedRule) as exc:game.engine.run(state,(Event(E.LAND_SPECIAL_TILE,payload=(("tile","CARD"),)),))
    assert exc.value.rule_ids==("inventory_reward_overflow",)


def test_invalid_probability_not_treated_as_illegal_action():
    game,state=game_fixture({"shop_distribution":[{"probability":"1/4","value":[]}]})
    with pytest.raises(ValueError,match="sum to 1"):apply_action(game,state,Action("REFRESH_SHOP"))


def test_generated_reward_does_not_collide_with_shop_identity():
    game,state=game_fixture()
    state=replace(state,shop_offers=(ShopOffer(10,BuildingInstance(2,B.PIGGY_BANK),8),))
    result,=game.engine.run(state,(Event(E.LAND_SPECIAL_TILE,payload=(("tile","CARD"),)),))
    assert result.state.inventory[0].instance_id!=2
    bought,=apply_action(game,result.state,Action("BUY",target=10))
    assert len(bought.state.inventory)==2
