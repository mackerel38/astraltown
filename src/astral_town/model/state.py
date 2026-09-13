from dataclasses import dataclass, fields, replace

from .building import BuildingInstance, ShopOffer
from .enums import Pack
from .enums import StandType
from .stand import StandInstance


@dataclass(frozen=True)
class ForcedDieEffect:
    face: int
    priority: int
    source: str

    def __post_init__(self):
        if type(self.face) is not int or type(self.priority) is not int:raise TypeError("Forced die face/priority must be integers")
        if self.face not in range(1, 7):
            raise ValueError("Die face must be 1..6")


@dataclass(frozen=True)
class GameState:
    difficulty_id: str
    stage_index: int
    turns_remaining: int
    wallet: int
    stage_progress: int
    player_position: int
    selected_packs: frozenset[Pack]
    unlocked_lots: frozenset[int]
    buildings: tuple[BuildingInstance, ...]
    inventory: tuple[BuildingInstance, ...]
    stands: tuple[StandInstance, ...]
    shop_offers: tuple[ShopOffer, ...]
    shop_refresh_count: int
    next_dice_count: int
    forced_die_effects: tuple[ForcedDieEffect, ...]
    rule_version: str
    movement_remaining: int = 0
    forced_stop: bool = False
    roll_id: int = 0
    last_roll: tuple[int, ...] = ()
    progress_score: int = 0
    status: str = "playing"
    phase: str = "management"
    stand_offers: tuple[StandType, ...] = ()

    def __post_init__(self):
        for name in ("selected_packs","unlocked_lots"):
            object.__setattr__(self,name,frozenset(getattr(self,name)))
        for name in ("buildings","inventory","stands","shop_offers","forced_die_effects","last_roll","stand_offers"):
            object.__setattr__(self,name,tuple(getattr(self,name)))
        integer_fields=("stage_index","turns_remaining","wallet","stage_progress","player_position","shop_refresh_count", "next_dice_count","movement_remaining","roll_id","progress_score")
        if any(type(getattr(self,name)) is not int for name in integer_fields):raise TypeError("State counters must be integers")
        if any(not isinstance(p,Pack) for p in self.selected_packs):raise TypeError("Selected packs must use Pack enum")
        if any(type(lot) is not int for lot in self.unlocked_lots):raise TypeError("Lot ids must be integers")
        if min(self.stage_index, self.turns_remaining, self.wallet, self.stage_progress,
               self.shop_refresh_count, self.movement_remaining, self.roll_id,self.progress_score) < 0:
            raise ValueError("Negative state field")
        if self.next_dice_count not in (1, 2):
            raise ValueError("Only one/two dice supported")
        if self.status not in {"playing", "cleared", "failed"} or self.phase not in {"management", "roll", "stand_selection", "terminal"}:
            raise ValueError("Invalid lifecycle status/phase")
        if any(face not in range(1, 7) for face in self.last_roll):
            raise ValueError("Invalid roll")
        owned = self.buildings + self.inventory
        if len({b.instance_id for b in owned}) != len(owned):
            raise ValueError("Duplicate building id")
        locations = [b.location for b in self.buildings]
        if len(set(locations)) != len(locations) or not set(locations) <= self.unlocked_lots:
            raise ValueError("Placed buildings require distinct unlocked lots")
        if any(b.location is not None for b in self.inventory):
            raise ValueError("Inventory must be unplaced")
        if len({s.instance_id for s in self.stands}) != len(self.stands):
            raise ValueError("Duplicate stand id")
        if len({o.offer_id for o in self.shop_offers}) != len(self.shop_offers):
            raise ValueError("Duplicate offer id")

    def building(self, instance_id: int) -> BuildingInstance:
        return next(b for b in self.buildings + self.inventory if b.instance_id == instance_id)

    def with_building(self, building: BuildingInstance) -> "GameState":
        self.building(building.instance_id)  # Reject missing ids.
        owned = tuple(building if b.instance_id == building.instance_id else b for b in self.buildings + self.inventory)
        return replace(self, buildings=tuple(b for b in owned if b.location is not None),
                       inventory=tuple(b for b in owned if b.location is None))

    def canonical_key(self) -> tuple:
        """Remove arbitrary identities, preserving every strategic counter.

        Forced-die source strings are semantic identifiers, never instance IDs.
        Execution traces retain original identity; keys are for search only.
        """
        def building_key(b):
            return tuple(getattr(b, f.name) for f in fields(b) if f.name != "instance_id")

        special = {"buildings", "inventory", "stands", "shop_offers"}
        base = tuple(getattr(self, f.name) for f in fields(self) if f.name not in special)
        return base + (
            tuple(sorted((building_key(b) for b in self.buildings), key=repr)),
            tuple(sorted((building_key(b) for b in self.inventory), key=repr)),
            tuple(sorted((s.stand_type, s.charge) for s in self.stands)),
            tuple(sorted(((building_key(o.building), o.price) for o in self.shop_offers), key=repr)),
        )
