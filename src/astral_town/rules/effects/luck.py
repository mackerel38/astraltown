from dataclasses import replace

from astral_town.model.enums import BuildingType as B, StandType as S
from astral_town.model.state import ForcedDieEffect
from astral_town.rules.economy import gain_xp, remove_building
from astral_town.rules.engine import deterministic
from .prosperity import charge


def install_luck(effects):
    registry=effects.registry

    def absorb(state,b,event):
        def apply(current,target):
            policy=registry.require("dice_tower_xp_transfer")
            amount=target.xp
            if policy=="total":amount+=sum(registry.require("xp_thresholds")[:target.level-1])
            elif policy!="residual":raise ValueError("Invalid Dice Tower XP transfer")
            tower=gain_xp(current.building(b.instance_id),amount,registry)
            tower=replace(tower,dice_coin_bonus=tower.dice_coin_bonus+effects.amount(b,"growth"))
            return deterministic(remove_building(current,target.instance_id).with_building(tower))
        return effects.random_target(state,effects.placed(state,kind={B.DICE_SCULPTURE}),"random_target_distribution",apply)

    def building(state,b,trigger,event):
        face=event.get("face")
        forced=trigger=="forced"
        if forced and b.building_type==B.HOLOGRAM_EXPERIENCE_HUT:
            trigger=registry.require("forced_HOLOGRAM_EXPERIENCE_HUT")
            if trigger=="no_effect":return deterministic(state)
            if trigger not in {"pass","roll"}:raise ValueError("Unsupported Hologram forced assumption")
            forced=False
        natural=trigger=="die"
        if b.building_type==B.DICE_SCULPTURE and (forced or natural and face==6):
            return effects.gain(state,effects.amount(b,"dice")+b.dice_coin_bonus,event)
        if b.building_type==B.FOUR_LEAF_INN:
            if forced or natural and face in (2,4,6):
                amount=effects.amount(b,"dice")+b.dice_coin_bonus
                if natural and face==6:
                    order=registry.require("four_leaf_growth_order")
                    growth=registry.require("FOUR_LEAF_INN.growth")
                    if order=="before_payout":amount+=growth
                    elif order!="after_payout":raise ValueError("Invalid Four-leaf growth order")
                    state=effects.bonus(state,(b,),"dice_coin_bonus",growth)
                return effects.gain(state,amount,event)
        if b.building_type==B.LUCKY_STAR_COIN_POND:
            if forced or natural and face==1:return deterministic(replace(state,next_dice_count=2))
            if trigger=="roll" and len(state.last_roll)==2:
                return effects.gain(state,effects.amount(b,"two")+b.dice_coin_bonus,event)
        if b.building_type==B.DICE_TOWER:
            if forced or natural and face==4:return absorb(state,b,event)
            if natural and face==6:return effects.gain(state,effects.amount(b,"dice")+b.dice_coin_bonus,event)
        if b.building_type==B.HOLOGRAM_EXPERIENCE_HUT:
            if trigger=="pass":return deterministic(replace(state,next_dice_count=2))
            if trigger=="roll" and len(state.last_roll)==2:
                return effects.gain(state,sum(state.last_roll)*effects.amount(b,"multiplier")+b.dice_coin_bonus,event)
        return deterministic(state)

    def stand(state,s,trigger,event):
        if s.stand_type==S.JASMINE and trigger=="roll":
            state,activated=charge(effects,state,s,registry.require("JASMINE.threshold"))
            return deterministic(replace(state,next_dice_count=2) if activated else state)
        if s.stand_type==S.FRIED_SHRIMP and trigger=="die" and event.get("face")==1:
            effect=ForcedDieEffect(registry.require("shrimp_face"),registry.require("shrimp_priority"),"FRIED_SHRIMP")
            return deterministic(replace(state,forced_die_effects=state.forced_die_effects+(effect,)))
        if s.stand_type==S.THREE_LEAF and trigger=="die" and event.get("face")==6:
            state,activated=charge(effects,state,s,registry.require("THREE_LEAF.threshold"))
            if activated:
                from astral_town.rules.catalog import required_packs
                from astral_town.model.enums import Pack
                allowed={kind for kind in B if Pack.LUCK in required_packs(kind,registry)}
                return effects.reward(state,"THREE_LEAF.distribution",allowed=allowed)
            return deterministic(state)
        return deterministic(state)

    effects.buildings.update({k:building for k in (B.DICE_SCULPTURE,B.FOUR_LEAF_INN,B.LUCKY_STAR_COIN_POND,B.DICE_TOWER,B.HOLOGRAM_EXPERIENCE_HUT)})
    effects.stands.update({k:stand for k in (S.JASMINE,S.FRIED_SHRIMP,S.THREE_LEAF)})
