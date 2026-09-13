"""Immutable economy primitives. Callers specify provenance of progress gain."""

from dataclasses import replace

from astral_town.model.building import BuildingInstance
from astral_town.model.enums import BuildingType
from .errors import IllegalAction


def gain_coin(state, amount: int, *, counts_for_progress: bool):
    if type(amount) is not int or amount < 0:
        raise ValueError("Coin gain must be a nonnegative integer")
    return replace(state, wallet=state.wallet + amount,
                   stage_progress=state.stage_progress + (amount if counts_for_progress else 0))


def spend_coin(state, amount: int):
    if type(amount) is not int or amount < 0 or amount > state.wallet:
        raise IllegalAction("Invalid spending amount / insufficient funds")
    return replace(state, wallet=state.wallet - amount)


def gain_xp(building, amount: int, registry):
    if type(amount) is not int or amount < 0:
        raise ValueError("XP gain must be nonnegative integer")
    if not amount:
        return building
    thresholds = registry.require("xp_thresholds")
    level, xp = building.level, building.xp + amount
    while level < 4 and xp >= thresholds[level - 1]:
        xp -= thresholds[level - 1]
        level += 1
    if level == 4 and xp:
        policy = registry.require("xp_max_storage")
        if policy == "discard":
            xp = 0
        elif policy != "retain":
            raise ValueError("xp_max_storage must be discard or retain")
    return replace(building, level=level, xp=xp)


def add_building(state, building: BuildingInstance, registry):
    if any(b.instance_id == building.instance_id for b in state.buildings + state.inventory):
        raise ValueError("Building id already owned")
    if building.location is None:
        capacity = registry.require("inventory_capacity")
        if len(state.inventory) >= capacity:
            raise IllegalAction("Inventory full; overflow behavior is not assumed")
        return replace(state, inventory=state.inventory + (building,))
    return replace(state, buildings=state.buildings + (building,))


def remove_building(state, instance_id):
    state.building(instance_id)
    return replace(state, buildings=tuple(b for b in state.buildings if b.instance_id != instance_id),
                   inventory=tuple(b for b in state.inventory if b.instance_id != instance_id))


def place_building(state, instance_id, location, registry):
    building = state.building(instance_id)
    if building.location == location:
        return state
    if location is None and len(state.inventory) >= registry.require("inventory_capacity"):
        raise IllegalAction("Inventory full")
    return state.with_building(replace(building, location=location))


def merge_buildings(state, target_id, source_id, registry):
    if target_id == source_id:
        raise IllegalAction("Cannot merge a building into itself")
    target, source = state.building(target_id), state.building(source_id)
    if source.building_type != target.building_type or source.level == 4:
        raise IllegalAction("Merge requires same type and non-Lv4 material")
    amount = registry.require("merge_base_xp")
    if source.xp or source.level > 1:
        policy = registry.require("merge_source_xp")
        if policy == "total":
            amount += sum(registry.require("xp_thresholds")[:source.level - 1]) + source.xp
        elif policy == "residual":
            amount += source.xp
        elif policy != "none":
            raise ValueError("Invalid source XP policy")
    counter_fields = ("dice_coin_bonus", "pass_coin_bonus", "stay_coin_bonus", "wish_stage_bonus", "captain_pass_bonus")
    if source.treasure_decay and source.building_type != BuildingType.TREASURE:
        raise ValueError("Decay on a non-Treasure cannot be interpreted")
    if any(getattr(source, field) for field in counter_fields) or source.custom_counters:
        policy = registry.require("merge_counters")
        if policy == "add":
            changes = {field: getattr(target, field) + getattr(source, field) for field in counter_fields}
            counters = dict(target.custom_counters)
            for key, value in source.custom_counters:
                counters[key] = counters.get(key, 0) + value
            target = replace(target, **changes, custom_counters=tuple(counters.items()))
        elif policy != "retain_target":
            raise ValueError("Invalid merge counter policy")
    target = gain_xp(target, amount, registry)
    return remove_building(state, source_id).with_building(target)
