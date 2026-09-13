from dataclasses import replace

import pytest

from astral_town.solver.calibration import calibrate,export_observations,load_observations
from astral_town.rules.registry import UnresolvedRule
from astral_town.rules.randomness import configured_distribution
from test_game import game_fixture


@pytest.mark.parametrize("suffix",[".csv",".json"])
def test_observations_round_trip_statistics(tmp_path,suffix):
    rows=[{"rule_id":"card_distribution","context":{"stage_index":0},"value":v} for v in ["A","A","B"]]
    path=tmp_path/("observations"+suffix)
    export_observations(rows,path)
    assert load_observations(path)==rows
    report,=calibrate(rows)
    assert report["sample_count"]==3
    assert report["confidence"]=="inferred" and report["method"]=="empirical"
    assert report["frequencies"][0]["frequency"]=="2/3"
    assert report["frequencies"][0]["standard_error"]>0
    lo,hi=report["frequencies"][0]["interval_95"]
    assert 0<lo<2/3<hi<1


def test_empirical_context_not_reused_at_other_stage():
    report,=calibrate([{"rule_id":"test_distribution","context":{"stage_index":0},"value":"A"}])
    game,state=game_fixture()
    game.registry.empirical={"test_distribution":report}
    assert configured_distribution(game.registry,"test_distribution",state)[0].state=="A"
    assert game.registry.exactness=="assumption-based"
    with pytest.raises(UnresolvedRule):configured_distribution(game.registry,"test_distribution",replace(state,stage_index=1))
