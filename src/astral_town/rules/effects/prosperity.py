from dataclasses import replace

from astral_town.model.enums import ActivationCause as C, BuildingType as B, Pack, StandType as S
from astral_town.rules.engine import deterministic
from .common import Effects


def install_prosperity(effects: Effects):
    registry = effects.registry

    def building(state, b, trigger, event):
        forced = trigger == "forced"
        if forced and b.building_type != B.LUCKY_COLOR_GATE:
            trigger = registry.require(f"forced_{b.building_type.value}")
            allowed={B.SMALL_WALLET:{"after"},B.WISHING_WELL:{"after"},B.MONEY_TREE:{"dice_payout","stay"},
                     B.HALL_OF_WEALTH:{"activate_neighbors","stay"},B.RABBIT_INN:{"pass"}}
            if trigger=="no_effect":return deterministic(state)
            if trigger not in allowed[b.building_type]:raise ValueError("Unsupported explicit forced-effect assumption")
        face = event.get("face")
        if b.building_type == B.SMALL_WALLET:
            if trigger == "after":
                return effects.gain(state,effects.amount(b,"after")+b.dice_coin_bonus,event)
        elif b.building_type == B.WISHING_WELL:
            if trigger == "after":
                return effects.gain(state,effects.amount(b,"after")+b.dice_coin_bonus+b.wish_stage_bonus,event)
            if trigger == "stage":
                return deterministic(effects.bonus(state,(b,),"wish_stage_bonus",registry.require("WISHING_WELL.stage")))
        elif b.building_type == B.MONEY_TREE:
            if trigger == "stay":
                return deterministic(effects.bonus(state,effects.adjacent(state,b,pack=Pack.PROSPERITY),"dice_coin_bonus",effects.amount(b,"stay")))
            if trigger == "dice_payout" or (trigger == "die" and face == 3):
                return effects.gain(state,effects.amount(b,"dice")+b.dice_coin_bonus,event)
        elif b.building_type == B.LUCKY_COLOR_GATE:
            if forced or (trigger == "die" and face in (1,6)):
                pack = Pack.PROSPERITY if forced or face == 1 else Pack.LUCK
                amount = len(effects.placed(state,pack=pack))*effects.amount(b,"dice")+b.dice_coin_bonus
                return effects.gain(state,amount,event)
        elif b.building_type == B.HALL_OF_WEALTH:
            if trigger == "stay":
                return deterministic(effects.bonus(state,effects.placed(state,pack=Pack.PROSPERITY),"dice_coin_bonus",effects.amount(b,"stay")))
            if trigger == "activate_neighbors" or (trigger == "roll" and any(face in (3,4) for face in state.last_roll)):
                return deterministic(state,*(effects.event(target,"forced",event,cause=C.FORCED_DICE_EFFECT)
                                             for target in effects.adjacent(state,b,pack=Pack.PROSPERITY)))
        elif b.building_type == B.RABBIT_INN and trigger == "pass":
            targets = effects.placed(state,pack=Pack.PROSPERITY,exclude=b.instance_id)
            from astral_town.model.outcomes import WeightedOutcome
            from astral_town.rules.engine import Transition
            strengthened=effects.random_target(state,targets,"random_target_distribution",
                lambda current,target:deterministic(effects.bonus(current,(target,),"dice_coin_bonus",effects.amount(b,"strength"))))
            return tuple(WeightedOutcome(o.probability,Transition(o.state.state,
                         effects.gain(o.state.state,effects.amount(b,"payout")+b.pass_coin_bonus,event)[0].state.followups)) for o in strengthened)
        return deterministic(state)

    def strengthen(state, event, amount):
        return effects.random_target(state,effects.placed(state,pack=Pack.PROSPERITY),"random_target_distribution",
            lambda current,target: deterministic(effects.bonus(current,(target,),"dice_coin_bonus",amount)))

    def stand(state, s, trigger, event):
        if (s.stand_type == S.MIMI and trigger == "after") or (s.stand_type == S.RABBIT and trigger == "start"):
            return strengthen(state,event,registry.require(f"{s.stand_type.value}.bonus"))
        if s.stand_type == S.RACCOON and trigger == "pass":
            b = state.building(event.get("building_id"))
            from astral_town.rules.catalog import required_packs
            if Pack.PROSPERITY in required_packs(b.building_type,registry):
                return effects.gain(state,registry.require("RACCOON.payout"),event,source="stand")
        if s.stand_type == S.UPDATE and trigger == "refresh":
            state, activated = charge(effects,state,s,registry.require("UPDATE.threshold"))
            if activated:
                return strengthen(state,event,registry.require("UPDATE.bonus"))
            return deterministic(state)
        return deterministic(state)

    effects.buildings.update({kind:building for kind in (B.SMALL_WALLET,B.WISHING_WELL,B.MONEY_TREE,B.LUCKY_COLOR_GATE,B.HALL_OF_WEALTH,B.RABBIT_INN)})
    effects.stands.update({kind:stand for kind in (S.MIMI,S.RABBIT,S.RACCOON,S.UPDATE)})


def charge(effects, state, stand, threshold, amount=1):
    if type(threshold) is not int or threshold <= 0:
        raise ValueError("Charge threshold must be a positive integer")
    value = stand.charge + amount
    activated = value >= threshold
    if activated:
        policy = effects.registry.require("stand_charge_consumption")
        if policy == "subtract":
            value -= threshold
        elif policy == "reset":
            value = 0
        else:
            raise ValueError("Invalid stand charge consumption")
    return replace(state,stands=tuple(replace(s,charge=value) if s.instance_id==stand.instance_id else s for s in state.stands)),activated
