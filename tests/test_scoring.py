from dataclasses import replace

import pytest

from astral_town.model.enums import BuildingType as B, EventType as E, StandType as S
from astral_town.model.events import Event
from astral_town.model.stand import StandInstance
from astral_town.rules.effects.neutral import install_neutral
from astral_town.rules.registry import RuleRegistry, UnresolvedRule
from astral_town.rules.scoring import final_score
from astral_town.samples import model_sample
from test_prosperity import setup


@pytest.mark.parametrize("wallet,amount",[(0,0),(49,0),(50,1),(149,2),(200,4)])
def test_credit_card(wallet,amount):
    state,engine,effects=setup((),stands=(StandInstance(10,S.CREDIT_CARD),))
    install_neutral(effects)
    result,=engine.run(replace(state,wallet=wallet),(Event(E.ACTIVATE_STAND,10,payload=(("trigger","turn_start"),)),))
    assert result.state.wallet==wallet+amount


def test_secret_book_can_select_lv4():
    state,engine,effects=setup((B.SMALL_WALLET,B.WISHING_WELL),{"random_target_distribution":"uniform","xp_max_storage":"discard"},(StandInstance(10,S.SECRET_BOOK),))
    install_neutral(effects)
    state=state.with_building(replace(state.building(0),level=4))
    outcomes=engine.run(state,(Event(E.ACTIVATE_STAND,10,payload=(("trigger","turn_start"),)),))
    assert len(outcomes)==2
    assert any(o.state==state for o in outcomes)
    assert any(o.state.building(1).xp==1 for o in outcomes)


def test_big_bag_explicit_copy_distribution():
    state,engine,effects=setup((B.SMALL_WALLET,B.WISHING_WELL),{"big_bag_distribution":"uniform","big_bag_copy_state":"full","inventory_capacity":5},(StandInstance(10,S.BIG_BAG),))
    install_neutral(effects)
    outcomes=engine.run(state,(Event(E.ACTIVATE_STAND,10,payload=(("trigger","start"),)),))
    assert len(outcomes)==2
    assert sum(o.probability for o in outcomes)==1
    assert {o.state.inventory[0].building_type for o in outcomes}=={B.SMALL_WALLET,B.WISHING_WELL}


def test_roller_uses_explicit_correspondence():
    from astral_town.model.board import Lot
    state,engine,effects=setup((B.SMALL_WALLET,),stands=(StandInstance(10,S.ROLLER),))
    effects.board=replace(effects.board,lots=(Lot(0,frozenset(),4),))
    install_neutral(effects)
    result,=engine.run(replace(state,player_position=4),(Event(E.ACTIVATE_STAND,10,payload=(("trigger","special"),)),))
    assert result.state.building(0).level==2


@pytest.mark.parametrize("rounding,half",[("floor",10),("ceil",11)])
def test_score_scope_and_rounding(rounding,half):
    state=replace(model_sample(),wallet=21,status="cleared",phase="terminal",progress_score=320)
    rules=RuleRegistry.builtin({"score_wallet_rounding":rounding,"score_building_value":"rarity_sell_base"})
    score=final_score(state,rules)
    assert (score.progress,score.star_coin,score.building)==(320,half,4)
    rules=RuleRegistry.builtin({"score_wallet_rounding":rounding,"score_building_value":"rarity_sell_base","score_scope":"owned"})
    assert final_score(state,rules).building==8


def test_unknown_rounding_not_legacy_fallback():
    with pytest.raises(UnresolvedRule) as exc:final_score(replace(model_sample(),status="cleared",wallet=21),RuleRegistry.builtin())
    assert exc.value.rule_ids==("score_wallet_rounding",)


def test_even_wallet_does_not_need_rounding_assumption():
    state=replace(model_sample(),wallet=20,status="cleared",buildings=(),inventory=())
    registry=RuleRegistry.builtin()
    assert final_score(state,registry).star_coin==10
    assert "score_wallet_rounding" not in registry.used
