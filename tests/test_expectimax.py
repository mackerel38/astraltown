from dataclasses import replace
from fractions import Fraction

from astral_town.model.building import BuildingInstance
from astral_town.model.enums import BuildingType as B
from astral_town.solver.expectimax import Expectimax
from astral_town.solver.evaluation import Metrics,utility
from test_game import game_fixture


def test_hand_computable_one_roll_and_transpositions():
    game,state=game_fixture()
    solver=Expectimax(game,horizon=1,management_depth=0,allowed_actions={"END_MANAGEMENT_AND_ROLL"})
    result=solver.solve(state)
    best=result.recommendations[0]
    assert best.metrics.expected_score==24  # 10 progress + floor(21/2) + 4 building
    assert best.metrics.clear_probability==1
    assert best.metrics.expected_wallet==21
    assert "assumption-based" in result.exactness
    # Identical state lookup reuses a transposition even with a renamed building.
    terminal=game.roll(state)[0].state
    solver._node(terminal,0,0)
    solver._node(replace(terminal,buildings=(replace(terminal.buildings[0],instance_id=99),)),0,0)
    assert solver.table.hits>=1


def test_two_roll_exact_rational_expectation():
    game,state=game_fixture({"stage_quotas":[100]})
    state=replace(state,buildings=(BuildingInstance(1,B.PIGGY_BANK,location=0),),turns_remaining=2)
    result=Expectimax(game,horizon=2,management_depth=0,allowed_actions={"END_MANAGEMENT_AND_ROLL"}).solve(state)
    metrics=result.recommendations[0].metrics
    assert metrics.expected_wallet==Fraction(62,3) # 20 + 2 rolls * 2/6
    assert metrics.expected_score==Fraction(43,3) # floor(wallet/2) + green Lv1 4
    assert metrics.clear_probability==0


def test_place_is_better_than_leaving_wallet_in_inventory():
    game,state=game_fixture()
    state=replace(state,buildings=(),inventory=(BuildingInstance(1,B.SMALL_WALLET),),turns_remaining=1)
    result=Expectimax(game,horizon=1,management_depth=1,allowed_actions={"END_MANAGEMENT_AND_ROLL","PLACE","SELL"}).solve(state)
    assert result.recommendations[0].actions[0].kind=="PLACE"
    assert len(result.recommendations)==3


def test_missing_rules_return_structured_blockers():
    game,state=game_fixture({"score_wallet_rounding":None})
    result=Expectimax(game,horizon=1,management_depth=0,allowed_actions={"END_MANAGEMENT_AND_ROLL"}).solve(state)
    assert result.missing_rule_ids==("score_wallet_rounding",)
    assert not result.recommendations and result.exactness=="unresolved"


def test_cancel_and_cutoff():
    game,state=game_fixture({"stage_quotas":[100]})
    result=Expectimax(game,cancel=lambda:True).solve(state)
    assert result.cancelled
    result=Expectimax(game,horizon=1,management_depth=0,allowed_actions={"END_MANAGEMENT_AND_ROLL"}).solve(state)
    assert "cutoff_heuristic" in result.missing_rule_ids


def test_objectives():
    m=Metrics(Fraction(10),Fraction(1,2))
    assert utility(m,"CLEAR_PROBABILITY")==Fraction(1,2)
    assert utility(m,"RISK_ADJUSTED_SCORE",risk_lambda=Fraction(4))==8
    assert utility(m,"EXPECTED_SCORE_WITH_CLEAR_CONSTRAINT",clear_threshold=Fraction(3,4)) is None
