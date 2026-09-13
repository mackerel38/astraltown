"""Typed JSON representation without Python object deserialization."""

from dataclasses import fields, is_dataclass
from enum import Enum
from fractions import Fraction

from . import enums
from .board import Board, Lot, Space
from .building import BuildingInstance, ShopOffer
from .events import ActivationKey, Event, EventLogEntry
from .outcomes import WeightedOutcome
from .stand import StandInstance
from .state import ForcedDieEffect, GameState

CLASSES = {c.__name__: c for c in (Board, Lot, Space, BuildingInstance, ShopOffer, ActivationKey,
                                  Event, EventLogEntry, WeightedOutcome, StandInstance, ForcedDieEffect, GameState)}
ENUMS = {name: cls for name, cls in vars(enums).items()
         if isinstance(cls, type) and issubclass(cls, Enum) and name != "StrEnum"}


def encode(value):
    if isinstance(value, Enum):
        return {"$enum": type(value).__name__, "value": value.value}
    if is_dataclass(value):
        return {"$type": type(value).__name__, **{f.name: encode(getattr(value, f.name)) for f in fields(value)}}
    if isinstance(value, Fraction):
        return {"$fraction": [value.numerator, value.denominator]}
    if isinstance(value, frozenset):
        return {"$set": [encode(v) for v in sorted(value, key=repr)]}
    if isinstance(value, tuple):
        return [encode(v) for v in value]
    if value is None or type(value) in (str, int, bool):
        return value
    raise TypeError(f"Unsupported value: {type(value)}")


def decode(value):
    if isinstance(value, list):
        return tuple(decode(v) for v in value)
    if isinstance(value, dict):
        if "$enum" in value:
            return ENUMS[value["$enum"]](value["value"])
        if "$fraction" in value:
            return Fraction(*value["$fraction"])
        if "$set" in value:
            return frozenset(decode(v) for v in value["$set"])
        if "$type" in value:
            return CLASSES[value["$type"]](**{k: decode(v) for k, v in value.items() if k != "$type"})
        raise ValueError("Unknown serialized object")
    return value
