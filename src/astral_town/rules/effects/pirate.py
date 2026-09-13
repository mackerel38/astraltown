from dataclasses import replace

from astral_town.model.enums import ActivationCause as C, BuildingType as B, EventType as E, Pack, StandType as S
from astral_town.model.events import Event
from astral_town.model.state import ForcedDieEffect
from astral_town.rules.engine import deterministic, Transition
from astral_town.model.outcomes import WeightedOutcome
from .prosperity import charge


def install_pirate(effects):
    registry=effects.registry

    def stays(state,targets,event):
        return deterministic(state,*(effects.event(target,"stay",event,cause=C.TRIGGERED_STAY) for target in targets))

    def building(state,b,trigger,event):
        if trigger=="forced":
            trigger=registry.require(f"forced_{b.building_type.value}")
        face=event.get("face")
        if b.building_type==B.TREASURE and trigger=="stay":
            amount=max(effects.amount(b,"stay")+b.stay_coin_bonus-b.treasure_decay,registry.require("treasure_minimum"))
            state=effects.bonus(state,(b,),"treasure_decay",registry.require("TREASURE.decay"))
            result,=effects.gain(state,amount,event)
            observers=tuple(Event(E.ACTIVATE_STAND,s.instance_id,event.cause,event.roll_id,event.die_index,
                                  (("trigger","treasure_stay"),),event.chain) for s in state.stands if s.stand_type==S.SHOVEL)
            return (WeightedOutcome(result.probability,Transition(result.state.state,result.state.followups+observers)),)
        if b.building_type==B.SAIL:
            if trigger in {"pass","stay"}:
                bonus=b.pass_coin_bonus if trigger=="pass" else b.stay_coin_bonus
                return effects.gain(state,effects.amount(b,trigger)+bonus,event)
            if trigger=="die" and face==4:return effects.gain(state,effects.amount(b,"dice")+b.dice_coin_bonus,event)
        if b.building_type==B.RUDDER:
            if trigger=="pass":
                return effects.random_target(state,effects.placed(state,kind={B.TREASURE}),"random_target_distribution",
                                             lambda current,target:stays(current,(target,),event))
            if trigger=="stay":
                results=effects.random_target(state,effects.placed(state,pack=Pack.LUCK,exclude=b.instance_id),"random_target_distribution",
                    lambda current,target:deterministic(current,effects.event(target,"forced",event,cause=C.FORCED_DICE_EFFECT)))
                payout,=effects.gain(state,effects.amount(b,"stay")+b.stay_coin_bonus,event)
                return tuple(WeightedOutcome(o.probability,Transition(o.state.state,payout.state.followups+o.state.followups)) for o in results)
        if b.building_type==B.ANCHOR and trigger=="pass":
            state=replace(state,forced_stop=True,movement_remaining=0,
                          forced_die_effects=state.forced_die_effects+(ForcedDieEffect(registry.require("anchor_face"),registry.require("anchor_priority"),"ANCHOR"),))
            return effects.gain(state,registry.require("anchor_pass")[b.level-1]+b.pass_coin_bonus,event)
        if b.building_type==B.CANNON:
            if trigger=="die" and face==4:return stays(state,effects.adjacent(state,b,kind={B.TREASURE,B.SAIL}),event)
            if trigger=="pass":
                rewards=effects.reward(state,"cannon_reward_distribution",allowed={B.TREASURE})
                return tuple(WeightedOutcome(o.probability,Transition(o.state.state,effects.gain(o.state.state,effects.amount(b,"pass")+b.pass_coin_bonus,event)[0].state.followups)) for o in rewards)
        if b.building_type==B.CAPTAIN_HAT:
            if trigger=="pass":return effects.gain(state,effects.amount(b,"pass")+b.pass_coin_bonus+b.captain_pass_bonus,event)
            if trigger=="stay":
                targets=effects.placed(state,kind={B.TREASURE})
                stay_events=tuple(effects.event(target,"stay",event,cause=C.TRIGGERED_STAY) for target in targets)
                remove_events=tuple(Event(E.REMOVE_BUILDING,target.instance_id,roll_id=event.roll_id) for target in targets)
                bonus=Event(E.BONUS,b.instance_id,roll_id=event.roll_id,payload=(("field","captain_pass_bonus"),("amount",len(targets)*effects.amount(b,"growth"))))
                return deterministic(state,*(stay_events+remove_events+(bonus,)))
        return deterministic(state)

    def stand(state,s,trigger,event):
        if s.stand_type==S.PIRATE_KING and trigger=="start":
            targets=effects.placed(state,pack=Pack.PIRATE)
            amount=registry.require("PIRATE_KING.bonus")
            state=effects.bonus(state,targets,"pass_coin_bonus",amount)
            state=effects.bonus(state,targets,"stay_coin_bonus",amount)
            return deterministic(state)
        if s.stand_type==S.SMALL_SHARK and trigger=="start":
            return effects.gain(state,len(effects.placed(state,pack=Pack.PIRATE)),event,source="stand")
        if s.stand_type==S.GREAT_SHARK and trigger=="die" and event.get("face")==4:
            state,activated=charge(effects,state,s,registry.require("GREAT_SHARK.threshold"))
            return stays(state,effects.placed(state,kind={B.TREASURE,B.SAIL}),event) if activated else deterministic(state)
        if s.stand_type==S.SHOVEL and trigger=="treasure_stay":
            state,activated=charge(effects,state,s,registry.require("SHOVEL.threshold"))
            return effects.gain(state,registry.require("SHOVEL.payout"),event,source="stand") if activated else deterministic(state)
        return deterministic(state)

    effects.buildings.update({k:building for k in (B.TREASURE,B.SAIL,B.RUDDER,B.ANCHOR,B.CANNON,B.CAPTAIN_HAT)})
    effects.stands.update({k:stand for k in (S.PIRATE_KING,S.GREAT_SHARK,S.SHOVEL,S.SMALL_SHARK)})
