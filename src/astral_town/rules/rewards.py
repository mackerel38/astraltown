"""Validation and allocation for explicit generated-instance templates."""

from dataclasses import fields

from astral_town.model.building import BuildingInstance
from astral_town.model.enums import BuildingType
from .catalog import eligible
from .registry import UnresolvedRule


def building_from_template(state,row,registry,offset=0):
    required={f.name for f in fields(BuildingInstance)}-{"instance_id","location"}
    if set(row)!=required:raise ValueError(f"Reward template needs exactly {sorted(required)}")
    data=dict(row)
    data["building_type"]=BuildingType(data["building_type"])
    data["custom_counters"]=tuple(tuple(p) for p in data["custom_counters"])
    if not eligible(data["building_type"],state.selected_packs,registry):raise ValueError("Impossible reward: pack not selected")
    ids=[b.instance_id for b in state.buildings+state.inventory]+[o.building.instance_id for o in state.shop_offers]
    return BuildingInstance(instance_id=max(ids,default=-1)+1+offset,location=None,**data)


def require_reward_capacity(state,registry):
    if len(state.inventory)>=registry.require("inventory_capacity"):
        raise UnresolvedRule("inventory_reward_overflow")
