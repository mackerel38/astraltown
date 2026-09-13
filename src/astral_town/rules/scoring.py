from dataclasses import dataclass
from fractions import Fraction
from math import ceil, floor

from astral_town.model.enums import StandType
from .catalog import sell_value


@dataclass(frozen=True)
class Score:
    progress: Fraction
    star_coin: Fraction
    building: Fraction

    @property
    def total(self):return self.progress+self.star_coin+self.building


def final_score(state,registry):
    if state.status=="playing":raise ValueError("Final score requires terminal state")
    half=Fraction(state.wallet,2)
    if half.denominator!=1:
        rounding=registry.require("score_wallet_rounding")
        if rounding=="ceil":half=Fraction(ceil(half))
        elif rounding=="floor":half=Fraction(floor(half))
        elif rounding!="fraction":raise ValueError("Invalid wallet rounding")
    scope=registry.require("score_scope")
    if scope=="placed":buildings=state.buildings
    elif scope=="owned":buildings=state.buildings+state.inventory
    else:raise ValueError("Invalid building score scope")
    formula=registry.require("score_building_value") if buildings else None
    total=0
    for b in buildings:
        if formula=="sell_total":value=sell_value(b,registry)
        elif formula=="rarity_sell_base":value=registry.require("sell_values")[registry.require(f"{b.building_type.value}.rarity")][b.level-1]
        else:raise ValueError("Invalid building score formula")
        if any(s.stand_type==StandType.PALUNAN for s in state.stands):
            interaction=registry.require("score_palunan")
            if interaction=="apply":
                from .effects.promotion import palunan_amount
                value=palunan_amount(value,registry,"palunan_sale")
            elif interaction!="ignore":raise ValueError("Invalid Palunan score policy")
        total+=value
    return Score(Fraction(state.progress_score),half,Fraction(total))
