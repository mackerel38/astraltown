"""Artificial fixtures. These values are NOT current starting defaults."""

from astral_town.model.building import BuildingInstance
from astral_town.model.enums import BuildingType, Pack
from astral_town.model.state import GameState


def model_sample():
    return GameState(
        difficulty_id="artificial", stage_index=0, turns_remaining=2,
        wallet=20, stage_progress=0, player_position=0,
        selected_packs=frozenset(Pack), unlocked_lots=frozenset({0, 1}),
        buildings=(BuildingInstance(1, BuildingType.SMALL_WALLET, location=0),),
        inventory=(BuildingInstance(2, BuildingType.PIGGY_BANK),), stands=(),
        shop_offers=(), shop_refresh_count=0, next_dice_count=1,
        forced_die_effects=(), rule_version="current-spec-2026-09-13",
    )
