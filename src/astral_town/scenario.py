"""Portable user-entered state, board and explicit assumptions."""

from astral_town.data.loader import load_file
from astral_town.model.serialization import decode,encode
from astral_town.model.state import GameState
from astral_town.model.board import Board
from astral_town.rules.registry import RuleRegistry
from astral_town.rules.game import Game


def from_scenario(data):
    state,board=decode(data["state"]),decode(data["board"])
    if not isinstance(state,GameState) or not isinstance(board,Board):raise ValueError("Scenario requires typed GameState and Board")
    registry=RuleRegistry.from_data(data["rules"],data.get("assumptions"),legacy=data.get("legacy",False)) if "rules" in data else RuleRegistry.builtin(data.get("assumptions"),legacy=data.get("legacy",False))
    registry.empirical=data.get("empirical_assumptions",{})
    game=Game(registry,board,accept_topology_assumption=data.get("accept_topology_assumption",False))
    return game,state


def load_scenario(path):return from_scenario(load_file(path))


def to_plain(value):
    """JSON output for result dataclasses (not rehydration)."""
    from dataclasses import fields,is_dataclass
    from fractions import Fraction
    from enum import Enum
    if isinstance(value,Enum):return value.value
    if isinstance(value,Fraction):return str(value)
    if is_dataclass(value):return {f.name:to_plain(getattr(value,f.name)) for f in fields(value)}
    if isinstance(value,(tuple,list,set,frozenset)):return [to_plain(v) for v in value]
    if isinstance(value,dict):return {k:to_plain(v) for k,v in value.items()}
    return value
