"""Generate explicit artificial scenarios; never current game defaults."""

import json
from dataclasses import replace
from pathlib import Path

from astral_town.model.board import Board,Lot,Space
from astral_town.model.building import BuildingInstance
from astral_town.model.enums import BuildingType as B,RuleConfidence as C,SpaceType as S
from astral_town.model.serialization import encode
from astral_town.samples import model_sample


def sample_data():
    board=Board(tuple(Space(i,S.START if i==0 else S.NORMAL,0 if i==1 else 1 if i==2 else None) for i in range(16)),
                (Lot(0,frozenset({1})),Lot(1,frozenset({0}))),C.INFERRED,"Artificial solver fixture; not observed topology")
    state=replace(model_sample(),buildings=(),inventory=(BuildingInstance(1,B.SMALL_WALLET),),turns_remaining=1)
    return {"description":"人工盤面・残り1ターン。配置/売却/ロールを比較する検証用シナリオ。現行初期状態ではありません。",
            "state":encode(state),"board":encode(board),"accept_topology_assumption":True,
            "allowed_actions":["END_MANAGEMENT_AND_ROLL","PLACE","SELL"],
            "assumptions":{"gain_progress_sources":["building","tile","stand","sale"],"roll_effect_order":"dice_then_roll",
                           "simultaneous_event_order":"board_then_stands","stage_clear_timing":"turn_end","stage_quotas":[1],
                           "stage_progress_scores":[10],"score_wallet_rounding":"floor","score_building_value":"rarity_sell_base",
                           "inventory_capacity":5,"shop_refill":"none","refresh_prices":[5,10,15],"shop_distribution":[{"probability":"1","value":[]}]}}


if __name__=="__main__":
    Path("examples/artificial.json").write_text(json.dumps(sample_data(),ensure_ascii=False,indent=2)+"\n")
