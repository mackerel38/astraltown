from dataclasses import replace

from test_game import game_fixture


def test_roll_cache_preserves_trace_identity_and_dependencies():
    game,state=game_fixture()
    first=game.roll(state)
    game.registry.used.clear()
    second=game.roll(state)
    assert second==first and game.roll_cache_hits==1
    assert "score_wallet_rounding" not in game.registry.used
    assert "stage_quotas" in game.registry.used
    assert game.exactness=="assumption-based"
    renamed=replace(state,buildings=(replace(state.buildings[0],instance_id=999),))
    third=game.roll(renamed)
    assert game.roll_cache_hits==1
    assert third[0].state.buildings[0].instance_id==999


def test_roll_cache_bounded_and_optional():
    game,state=game_fixture()
    game.roll_cache_limit=1
    game.roll(state);game.roll(replace(state,wallet=30))
    assert len(game.roll_cache)==1
    game.roll_cache.clear();game.roll_cache_limit=0
    game.roll(state)
    assert not game.roll_cache
