from dataclasses import replace

from astral_town.model.building import BuildingInstance,ShopOffer
from astral_town.model.enums import BuildingType as B
from astral_town.solver.management_search import enumerate_plans,wallet_dominates,Action,apply_action
from test_game import game_fixture


def test_equivalent_action_orders_deduplicate():
    game,state=game_fixture()
    state=replace(state,inventory=(BuildingInstance(2,B.SMALL_WALLET),))
    candidates=enumerate_plans(game,state,max_actions=2,max_states=100)
    keys=[plan.state.canonical_key() for plan in candidates.plans]
    assert len(keys)==len(set(keys))
    assert any(len(p.state.buildings)==2 for p in candidates.plans)
    assert candidates.truncated


def test_dominance_preserves_progress_shop_and_bonus():
    _,state=game_fixture()
    poorer=replace(state,wallet=state.wallet-1)
    assert wallet_dominates(state,poorer)
    assert not wallet_dominates(state,replace(poorer,stage_progress=1))
    assert not wallet_dominates(state,replace(poorer,shop_offers=(ShopOffer(0,BuildingInstance(3,B.SMALL_WALLET),8),)))
    assert not wallet_dominates(state,poorer.with_building(replace(poorer.buildings[0],dice_coin_bonus=1)))


def test_select_stand():
    game,state=game_fixture({"stage_quotas":[1,1],"stage_progress_scores":[10,20],"stage_rolls":[2,3],"stage_progress_reset":"zero",
                             "stand_offers":[{"probability":"1","value":["CREDIT_CARD"]}]})
    after=game.roll(state)[0].state
    result,=apply_action(game,after,Action("SELECT_STAND",target=0))
    assert result.state.phase=="management"
    assert len(result.state.stands)==1
