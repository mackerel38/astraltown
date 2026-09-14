"""Review regressions: search resources and management depth are not game rules."""

from dataclasses import replace
from importlib import import_module

import pytest

from astral_town.model.building import BuildingInstance
from astral_town.model.enums import BuildingType as B, StandType as S, EventType as E
from astral_town.model.stand import StandInstance
from astral_town.model.events import Event
from astral_town.rules.errors import IllegalAction
from astral_town.rules.registry import UnresolvedRule
from astral_town.rules.scoring import final_score
from astral_town.solver.expectimax import Expectimax
from astral_town.solver.management_search import Action, apply_action, enumerate_plans
from astral_town.solver.rollout import rollout
from test_game import game_fixture
from test_promotion import promotion


@pytest.mark.parametrize("objective", ["EXPECTED_SCORE", "EXPECTED_SCORE_WITH_CLEAR_CONSTRAINT"])
def test_stand_selection_preserves_one_management_action(objective):
    game, state = game_fixture()
    state = replace(state, phase="stand_selection", stand_offers=(S.CREDIT_CARD,), turns_remaining=1,
                    buildings=(), inventory=(BuildingInstance(1, B.SMALL_WALLET),))
    result = Expectimax(game, horizon=1, management_depth=1, objective=objective,
                       allowed_actions={"SELECT_STAND", "PLACE", "END_MANAGEMENT_AND_ROLL"}).solve(state)
    assert not result.missing_rule_ids
    assert result.recommendations[0].metrics.expected_score == 24
    assert result.recommendations[0].metrics.clear_probability == 1
    if objective == "EXPECTED_SCORE":
        assert [a.kind for a in result.recommendations[0].actions] == ["SELECT_STAND", "PLACE", "END_MANAGEMENT_AND_ROLL"]
    plans = enumerate_plans(game, state, max_actions=1)
    assert any([a.kind for a in p.actions] == ["SELECT_STAND", "PLACE", "END_MANAGEMENT_AND_ROLL"] for p in plans.plans)


@pytest.mark.parametrize("objective", ["EXPECTED_SCORE", "EXPECTED_SCORE_WITH_CLEAR_CONSTRAINT"])
def test_duplicate_stand_is_illegal_and_other_candidate_is_searched(objective):
    game, state = game_fixture({"stand_selection_duplicates": "reject"})
    state = replace(state, phase="stand_selection", stands=(StandInstance(10, S.CREDIT_CARD),),
                    stand_offers=(S.CREDIT_CARD, S.RACCOON))
    with pytest.raises(IllegalAction):apply_action(game, state, Action("SELECT_STAND", target=0))
    result = Expectimax(game, horizon=1, management_depth=0, objective=objective,
                       allowed_actions={"SELECT_STAND", "END_MANAGEMENT_AND_ROLL"}).solve(state)
    assert not result.missing_rule_ids
    assert result.recommendations[0].actions[0] == Action("SELECT_STAND", target=1)


@pytest.mark.parametrize("objective", ["EXPECTED_SCORE", "EXPECTED_SCORE_WITH_CLEAR_CONSTRAINT"])
def test_search_budget_is_not_a_missing_rule(objective):
    game, state = game_fixture()
    result = Expectimax(game, horizon=1, management_depth=0, node_budget=1, objective=objective,
                       allowed_actions={"END_MANAGEMENT_AND_ROLL"}).solve(state)
    assert result.budget_exhausted
    assert result.exactness == "budget-exhausted"
    assert result.nodes == 1
    assert not result.missing_rule_ids and not game.registry.missing
    assert not result.recommendations


def test_budget_keeps_only_completed_root_candidate():
    game, state = game_fixture()
    result = Expectimax(game, horizon=1, management_depth=1, node_budget=6,
                       allowed_actions={"END_MANAGEMENT_AND_ROLL", "SELL"}).solve(state)
    assert result.budget_exhausted and not result.missing_rule_ids
    assert "bounded-search" in result.exactness
    assert len(result.recommendations) == 1
    assert result.recommendations[0].actions == (Action("END_MANAGEMENT_AND_ROLL"),)
    assert result.next_best_gap is None


@pytest.mark.parametrize("kind,base,bonus", [(B.PIGGY_BANK, 8, 8), (B.PIGLET_BANK, 16, 15)])
@pytest.mark.parametrize("scope", ["total", "base_only"])
def test_palunan_sale_scope_and_independent_score(kind, base, bonus, scope):
    from math import floor
    from fractions import Fraction
    assumptions = {"palunan_sale": "5/4", "palunan_rounding": "floor", "palunan_sale_scope": scope,
                   "gain_progress_sources": ["sale"], "score_building_value": "sell_total", "score_palunan": "ignore"}
    state, engine, _ = promotion((kind,), assumptions, stands=(StandInstance(10, S.PALUNAN),))
    state = state.with_building(replace(state.building(0), level=2))
    sold, = engine.run(state, (Event(E.SELL_BUILDING, 0),))
    expected = floor(Fraction(base + bonus) * Fraction(5,4)) if scope == "total" else floor(Fraction(base)*Fraction(5,4)) + bonus
    assert sold.state.wallet - state.wallet == expected
    assert sold.state.stage_progress - state.stage_progress == expected
    assert final_score(replace(state, status="cleared"), engine.registry).building == base + bonus


def test_palunan_scope_stays_unknown_without_assumption():
    state, engine, _ = promotion((B.PIGGY_BANK,), {"palunan_sale":"5/4", "palunan_rounding":"floor"},
                                 stands=(StandInstance(10,S.PALUNAN),))
    with pytest.raises(UnresolvedRule, match="palunan_sale_scope"):
        engine.run(state, (Event(E.SELL_BUILDING,0),))


@pytest.mark.parametrize("first_kind", ["PLACE", "END_MANAGEMENT_AND_ROLL"])
@pytest.mark.parametrize("max_rolls", [0, 1, 2, 3])
def test_rollout_total_roll_cap_includes_first_action(monkeypatch, first_kind, max_rolls):
    game, state = game_fixture({"stage_quotas": [1000]})
    state = replace(state, turns_remaining=10, buildings=(), inventory=(BuildingInstance(1,B.SMALL_WALLET),))
    first = Action(first_kind, 1, 0) if first_kind == "PLACE" else Action(first_kind)
    monkeypatch.setattr(import_module("astral_town.solver.rollout"), "actions", lambda *_:(first,))
    original = game.roll
    calls = []
    def counted(current):
        calls.append(current.roll_id)
        return original(current)
    monkeypatch.setattr(game,"roll",counted)
    result = rollout(game,state,iterations=1,max_rolls=max_rolls)
    assert len(calls) == max_rolls
    assert result.budget_exhausted and not result.missing_rule_ids
    assert result.exactness == "budget-exhausted"
    assert not result.recommendations  # No terminal score fabricated for an incomplete trajectory.


def test_rollout_terminal_on_exact_roll_limit_is_scored():
    game, state = game_fixture({"stage_quotas":[1000]})
    result = rollout(game,replace(state,turns_remaining=2),iterations=1,max_rolls=2,
                     allowed_actions={"END_MANAGEMENT_AND_ROLL"})
    assert not result.budget_exhausted and not result.missing_rule_ids
    assert result.recommendations[0].samples == 1
