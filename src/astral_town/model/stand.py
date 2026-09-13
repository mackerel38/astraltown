from dataclasses import dataclass

from .enums import StandType


@dataclass(frozen=True)
class StandInstance:
    instance_id: int
    stand_type: StandType
    charge: int = 0

    def __post_init__(self):
        if not isinstance(self.stand_type, StandType):
            raise TypeError("stand_type must be StandType")
        if self.instance_id < 0 or self.charge < 0:
            raise ValueError("Invalid stand identity/charge")
