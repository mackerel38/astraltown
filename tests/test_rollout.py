from dataclasses import replace

from astral_town.model.building import BuildingInstance
from astral_town.model.enums import BuildingType as B
from astral_town.solver.rollout import rollout
from test_game import game_fixture


def test_reproducible_rollout_and_interval():
    game,state=game_fixture({"stage_quotas":[100]})
    state=replace(state,buildings=(BuildingInstance(1,B.PIGGY_BANK,location=0),),turns_remaining=1)
    a=rollout(game,state,iterations=40,seed=18,allowed_actions={"END_MANAGEMENT_AND_ROLL"})
    b=rollout(game,state,iterations=40,seed=18,allowed_actions={"END_MANAGEMENT_AND_ROLL"})
    assert a==b
    assert a.exactness=="simulation-estimated"
    estimate=a.recommendations[0]
    assert estimate.samples==40
    assert estimate.score_interval_95 is not None
    assert estimate.score_interval_95[0]<=float(estimate.metrics.expected_score)<=estimate.score_interval_95[1]
    assert state.wallet==20 and state.buildings[0].xp==0


def test_cancel_cleanly_and_single_sample_interval():
    game,state=game_fixture()
    result=rollout(game,state,cancel=lambda:True)
    assert result.cancelled and not result.recommendations
    result=rollout(game,state,iterations=1,allowed_actions={"END_MANAGEMENT_AND_ROLL"})
    assert result.recommendations[0].score_interval_95 is None
