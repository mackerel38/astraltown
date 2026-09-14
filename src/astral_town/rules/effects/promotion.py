from dataclasses import replace
from fractions import Fraction
from itertools import combinations, product

from astral_town.model.enums import BuildingType as B, EventType as E, StandType as S
from astral_town.model.events import Event
from astral_town.model.outcomes import WeightedOutcome, validate_distribution
from astral_town.rules.economy import gain_xp, remove_building, gain_coin
from astral_town.rules.engine import Transition, deterministic
from astral_town.rules.catalog import sale_components
from .prosperity import charge


def install_promotion(effects):
    registry=effects.registry

    def xp(state, targets, amount):
        for target in targets:
            state=state.with_building(gain_xp(state.building(target.instance_id),amount,registry))
        return state

    def building(state,b,trigger,event):
        if trigger=="forced":
            trigger=registry.require(f"forced_{b.building_type.value}")
        if b.building_type==B.PIGGY_BANK and trigger=="die" and event.get("face")==1:
            return effects.gain(xp(state,(b,),registry.require("PIGGY_BANK.xp")),registry.require("PIGGY_BANK.dice")+b.dice_coin_bonus,event)
        if b.building_type==B.PIGLET_BANK and trigger=="after":
            return deterministic(xp(state,(b,),registry.require("PIGLET_BANK.xp")))
        if b.building_type==B.SMALL_BOOKSTORE:
            if trigger=="stay":
                return deterministic(xp(state,(b,)+effects.adjacent(state,b),effects.amount(b,"xp")))
            if trigger=="pass":
                return effects.gain(state,effects.amount(b,"pass")+b.pass_coin_bonus,event)
        if b.building_type==B.BECKONING_CAT_VAULT:
            if trigger=="after":
                # Owned vs placed scope is not silently guessed.
                scope=registry.require("vault_xp_scope")
                targets=state.buildings+state.inventory if scope=="owned" else state.buildings if scope=="placed" else None
                if targets is None: raise ValueError("Invalid vault XP scope")
                return deterministic(xp(state,tuple(t for t in targets if t.building_type in {B.PIGGY_BANK,B.PIGLET_BANK}),effects.amount(b,"xp")))
            if trigger=="pass":
                return effects.gain(state,effects.amount(b,"pass")+b.pass_coin_bonus,event)
        if b.building_type==B.FOX_ANTIQUE_SHOP:
            if trigger=="die" and event.get("face")==5:
                amount=effects.amount(b,"xp")
                count=effects.amount(b,"targets")
                targets=effects.placed(state)
                if not registry.require("fox_self_target"):
                    targets=tuple(t for t in targets if t.instance_id!=b.instance_id)
                mode=registry.require("multi_target_sampling")
                if registry.require("random_target_distribution")!="uniform":
                    raise ValueError("Fox requires a configured tuple distribution for nonuniform targets")
                if mode=="without_replacement":
                    if count>len(targets):
                        if registry.require("insufficient_random_targets")!="all": raise ValueError("Unsupported insufficient target policy")
                        count=len(targets)
                    selections=tuple(combinations(targets,count))
                elif mode=="with_replacement":
                    selections=tuple(product(targets,repeat=count))
                else: raise ValueError("Invalid multi-target sampling")
                if not selections: raise ValueError("Empty Fox target distribution")
                state=xp(state,(b,),amount)
                return validate_distribution(WeightedOutcome(Fraction(1,len(selections)),Transition(xp(state,selection,amount))) for selection in selections)
            if trigger=="pass":
                return effects.reward(state,"fox_generation_distribution",allowed={B.PIGGY_BANK,B.PIGLET_BANK})
        return deterministic(state)

    def stand(state,s,trigger,event):
        if s.stand_type==S.PIG and trigger=="sale":
            state,activated=charge(effects,state,s,registry.require("PIG.threshold"))
            if activated:return effects.reward(state,"pig_reward_distribution",allowed={B.PIGLET_BANK})
        # Palunan is evaluated by purchase/sale/score rather than event routing.
        return deterministic(state)

    def sell(state,event):
        b=state.building(event.source_id)
        base,bonus=sale_components(b,registry)
        amount=base+bonus
        if any(s.stand_type==S.PALUNAN for s in state.stands):
            scope=registry.require("palunan_sale_scope")
            if scope=="total":amount=palunan_amount(amount,registry,"palunan_sale")
            elif scope=="base_only":amount=palunan_amount(base,registry,"palunan_sale")+bonus
            else:raise ValueError("Invalid Palunan sale scope")
        state=remove_building(state,b.instance_id)
        if b.building_type in {B.PIGGY_BANK,B.PIGLET_BANK}:
            state=effects.bonus(state,effects.placed(state,kind={B.BECKONING_CAT_VAULT}),"pass_coin_bonus",registry.require("BECKONING_CAT_VAULT.sale_bonus"))
        state=gain_coin(state,amount,counts_for_progress="sale" in registry.require("gain_progress_sources"))
        observers=tuple(Event(E.ACTIVATE_STAND,s.instance_id,payload=(("trigger","sale"),)) for s in state.stands if s.stand_type==S.PIG)
        return deterministic(state,*observers)

    effects.buildings.update({k:building for k in (B.PIGGY_BANK,B.PIGLET_BANK,B.SMALL_BOOKSTORE,B.BECKONING_CAT_VAULT,B.FOX_ANTIQUE_SHOP)})
    effects.stands.update({S.PIG:stand,S.PALUNAN:stand})
    effects.engine.handlers[E.SELL_BUILDING]=sell


def palunan_amount(amount,registry,key):
    from math import ceil, floor
    value=Fraction(amount)*Fraction(registry.require(key))
    mode=registry.require("palunan_rounding")
    if mode=="floor":return floor(value)
    if mode=="ceil":return ceil(value)
    if mode=="exact_integer" and value.denominator==1:return int(value)
    raise ValueError("Unsupported/nonintegral Palunan rounding")
