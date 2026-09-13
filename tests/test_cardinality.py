from dataclasses import replace

import pytest

from astral_town.model.building import BuildingInstance
from astral_town.model.enums import BuildingType as B
from astral_town.rules.registry import UnresolvedRule
from test_game import game_fixture


def test_unknown_repeated_piggy_trigger_is_not_assumed_per_die():
    game,state=game_fixture()
    state=replace(state,next_dice_count=2,buildings=(BuildingInstance(1,B.PIGGY_BANK,location=0),))
    with pytest.raises(UnresolvedRule) as exc:game.roll(state)
    assert exc.value.rule_ids==("PIGGY_BANK.natural_cardinality",)


@pytest.mark.parametrize("cardinality,payout",[("PER_DIE",4),("PER_ROLL",2)])
def test_explicit_duplicate_trigger_cardinality(cardinality,payout):
    game,state=game_fixture({"PIGGY_BANK.natural_cardinality":cardinality})
    state=replace(state,next_dice_count=2,buildings=(BuildingInstance(1,B.PIGGY_BANK,location=0),),turns_remaining=1)
    result=next(o for o in game.roll(state) if o.state.last_roll==(1,1))
    assert result.state.wallet==20+payout


def test_single_die_does_not_require_duplicate_cardinality():
    game,state=game_fixture()
    state=replace(state,buildings=(BuildingInstance(1,B.PIGGY_BANK,location=0),))
    assert len(game.roll(state))==6
    assert "PIGGY_BANK.natural_cardinality" not in game.registry.used
