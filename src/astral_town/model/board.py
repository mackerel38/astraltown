from dataclasses import dataclass

from .enums import RuleConfidence, SpaceType


@dataclass(frozen=True)
class Space:
    id: int
    type: SpaceType
    lot_id: int | None = None


@dataclass(frozen=True)
class Lot:
    id: int
    adjacent_lots: frozenset[int]
    corresponding_special_tile: int | None = None

    def __post_init__(self):object.__setattr__(self,"adjacent_lots",frozenset(self.adjacent_lots))


@dataclass(frozen=True)
class Board:
    """Space tuple is traversal order. No default real-game topology."""

    spaces: tuple[Space, ...]
    lots: tuple[Lot, ...]
    confidence: RuleConfidence
    source: str

    def __post_init__(self):
        object.__setattr__(self,"spaces",tuple(self.spaces))
        object.__setattr__(self,"lots",tuple(self.lots))
        space_ids = {s.id for s in self.spaces}
        lot_ids = {lot.id for lot in self.lots}
        if not self.spaces or len(space_ids) != len(self.spaces):
            raise ValueError("Empty board or duplicate space")
        if len(lot_ids) != len(self.lots):
            raise ValueError("Duplicate lot")
        used = [s.lot_id for s in self.spaces if s.lot_id is not None]
        if not set(used) <= lot_ids or len(used) != len(set(used)):
            raise ValueError("Invalid space/lot mapping")
        by_id = {lot.id: lot for lot in self.lots}
        for lot in self.lots:
            if not lot.adjacent_lots <= lot_ids or lot.id in lot.adjacent_lots:
                raise ValueError("Invalid adjacency")
            if any(lot.id not in by_id[n].adjacent_lots for n in lot.adjacent_lots):
                raise ValueError("Adjacency must be symmetric")
            if lot.corresponding_special_tile is not None and lot.corresponding_special_tile not in space_ids:
                raise ValueError("Unknown corresponding tile")

    def next_space(self, position: int) -> Space:
        ids = tuple(s.id for s in self.spaces)
        return self.spaces[(ids.index(position) + 1) % len(ids)]
