from dataclasses import dataclass

from .enums import BuildingType


@dataclass(frozen=True)
class BuildingInstance:
    instance_id: int
    building_type: BuildingType
    level: int = 1
    xp: int = 0
    location: int | None = None
    dice_coin_bonus: int = 0
    pass_coin_bonus: int = 0
    stay_coin_bonus: int = 0
    wish_stage_bonus: int = 0
    treasure_decay: int = 0
    captain_pass_bonus: int = 0
    custom_counters: tuple[tuple[str, int], ...] = ()

    def __post_init__(self):
        if not isinstance(self.building_type, BuildingType):
            raise TypeError("building_type must be BuildingType")
        if any(type(v) is not int for v in (self.instance_id,self.level,self.xp)):raise TypeError("Building id/level/XP must be integers")
        if not 1 <= self.level <= 4 or self.xp < 0 or self.instance_id < 0:
            raise ValueError("Invalid building identity/level/XP")
        if len(dict(self.custom_counters)) != len(self.custom_counters):
            raise ValueError("Duplicate counter")
        object.__setattr__(self, "custom_counters", tuple(sorted(tuple(pair) for pair in self.custom_counters)))


@dataclass(frozen=True)
class ShopOffer:
    offer_id: int
    building: BuildingInstance
    price: int

    def __post_init__(self):
        if self.price < 0 or self.building.location is not None:
            raise ValueError("Invalid shop offer")
