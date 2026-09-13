from dataclasses import replace
from fractions import Fraction

import pytest

from astral_town.model.board import Board, Lot, Space
from astral_town.model.enums import BuildingType as B, EventType as E, RuleConfidence as C, SpaceType as S
from astral_town.rules.game import Game
from astral_town.rules.registry import RuleRegistry, UnresolvedRule
from astral_town.samples import model_sample
from test_promotion import template


def game_fixture(extra=None):
    assumptions={"gain_progress_sources":["building","tile","stand","sale"],"roll_effect_order":"dice_then_roll",
                 "simultaneous_event_order":"board_then_stands","stage_clear_timing":"turn_end","stage_quotas":[1],
                 "stage_progress_scores":[10],"score_wallet_rounding":"floor","score_building_value":"rarity_sell_base",
                 "inventory_capacity":5,"shop_refill":"none","refresh_prices":[5,10,15],
                 "shop_distribution":[{"probability":"1","value":[]}],"stage_rolls":[2],
                 "card_distribution":[{"probability":"1","value":template(B.SMALL_WALLET)}]}
    assumptions.update(extra or {})
    board=Board(tuple(Space(i,S.START if i==0 else S.NORMAL,0 if i==1 else 1 if i==2 else None) for i in range(16)),
                (Lot(0,frozenset({1})),Lot(1,frozenset({0}))),C.INFERRED,"artificial integration fixture")
    game=Game(RuleRegistry.builtin(assumptions),board,accept_topology_assumption=True)
    return game,replace(model_sample(),inventory=())


def test_full_turn_chances_and_trace():
    game,state=game_fixture()
    results=game.roll(state)
    assert len(results)==6
    assert results[0].events[0].before==state
    assert game.engine.replay(state,results[0].events)==results[0].state
    assert all(o.probability==Fraction(1,6) for o in results)
    assert all(o.state.status=="cleared" and o.state.wallet==21 and o.state.progress_score==10 for o in results)
    assert all(o.state.turns_remaining==1 for o in results)
    types=[e.event.type for e in results[0].events]
    assert types.index(E.AFTER_ROLL)<types.index(E.MOVE_BEGIN)<types.index(E.TURN_END)<types.index(E.GAME_CLEAR)
    assert game.exactness=="assumption-based"


def test_unknown_unvisited_does_not_block():
    game,state=game_fixture({"card_distribution":None})
    assert len(game.roll(state))==6


def test_card_distribution_blocks_only_card_branch():
    game,state=game_fixture({"card_distribution":None})
    board=replace(game.board,spaces=tuple(replace(s,type=S.CARD) if s.id==4 else s for s in game.board.spaces))
    game=Game(game.registry,board,accept_topology_assumption=True)
    with pytest.raises(UnresolvedRule) as exc:game.roll(state)
    assert exc.value.rule_ids==("card_distribution",)


def test_stage_transition_and_stand_offers():
    game,state=game_fixture({"stage_quotas":[1,1],"stage_progress_scores":[10,20],"stage_rolls":[2,3],"stage_progress_reset":"zero",
                             "stand_offers":[{"probability":"1","value":["MIMI","CREDIT_CARD"]}]})
    result=game.roll(state)[0].state
    assert result.stage_index==1 and result.turns_remaining==3 and result.stage_progress==0
    assert result.phase=="stand_selection" and len(result.stand_offers)==2


def test_fail_at_last_turn():
    game,state=game_fixture({"stage_quotas":[100]})
    outcomes=game.roll(replace(state,turns_remaining=1))
    assert all(o.state.status=="failed" for o in outcomes)
