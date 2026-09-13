from dataclasses import replace

from astral_town.model.enums import StandType as S
from astral_town.rules.economy import add_building, gain_xp
from astral_town.rules.engine import deterministic


def install_neutral(effects):
    registry=effects.registry

    def stand(state,s,trigger,event):
        if s.stand_type==S.CREDIT_CARD and trigger=="turn_start":
            return effects.gain(state,state.wallet//registry.require("CREDIT_CARD.divisor"),event,source="stand")
        if s.stand_type==S.SECRET_BOOK and trigger=="turn_start":
            return effects.random_target(state,effects.placed(state),"random_target_distribution",
                lambda current,target:deterministic(current.with_building(gain_xp(target,registry.require("SECRET_BOOK.xp"),registry))))
        if s.stand_type==S.BIG_BAG and trigger=="start":
            def copy(current,target):
                from astral_town.rules.rewards import require_reward_capacity
                require_reward_capacity(current,registry)
                mode=registry.require("big_bag_copy_state")
                instance_id=max((b.instance_id for b in current.buildings+current.inventory),default=-1)+1
                if mode=="full":building=replace(target,instance_id=instance_id,location=None)
                elif mode=="template":
                    from astral_town.model.building import BuildingInstance
                    data=dict(registry.require("big_bag_template"))
                    building=BuildingInstance(instance_id=instance_id,building_type=target.building_type,location=None,**data)
                else:raise ValueError("Unknown Big Bag copy policy")
                return deterministic(add_building(current,building,registry))
            return effects.random_target(state,effects.placed(state),"big_bag_distribution",copy)
        if s.stand_type==S.ROLLER and trigger=="special":
            lot_ids={lot.id for lot in effects.board.lots if lot.corresponding_special_tile==state.player_position}
            if len(lot_ids)!=1:
                from astral_town.rules.registry import UnresolvedRule
                raise UnresolvedRule("roller_corresponding_lot")
            targets=tuple(b for b in state.buildings if b.location in lot_ids)
            if not targets:return deterministic(state)
            return deterministic(state.with_building(gain_xp(targets[0],registry.require("ROLLER.xp"),registry)))
        return deterministic(state)

    effects.stands.update({k:stand for k in (S.BIG_BAG,S.ROLLER,S.SECRET_BOOK,S.CREDIT_CARD)})
