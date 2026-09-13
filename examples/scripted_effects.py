"""Run: python examples/scripted_effects.py. Artificial, explicitly assumed inputs."""

from dataclasses import replace

from astral_town.model.board import Board, Lot, Space
from astral_town.model.building import BuildingInstance
from astral_town.model.enums import BuildingType as B, EventType as E, RuleConfidence, SpaceType
from astral_town.model.events import Event
from astral_town.rules.engine import EventEngine
from astral_town.rules.effects.common import Effects
from astral_town.rules.effects.prosperity import install_prosperity
from astral_town.rules.effects.promotion import install_promotion
from astral_town.rules.movement import install_movement
from astral_town.rules.registry import RuleRegistry
from astral_town.samples import model_sample


def run():
    registry=RuleRegistry.builtin({"gain_progress_sources":["building"],"simultaneous_event_order":"board_then_stands"})
    state=replace(model_sample(),buildings=(BuildingInstance(0,B.SMALL_WALLET,location=0),BuildingInstance(1,B.PIGGY_BANK,location=1)),inventory=(),last_roll=(1,),roll_id=1)
    board=Board(tuple(Space(i,SpaceType.START if i==0 else SpaceType.NORMAL,i-1 if i in (1,2) else None) for i in range(16)),
                (Lot(0,frozenset({1})),Lot(1,frozenset({0}))),RuleConfidence.INFERRED,"Artificial demo topology")
    engine=EventEngine(registry)
    install_movement(engine,board,accept_topology_assumption=True)
    effects=Effects(engine,board)
    install_prosperity(effects)
    install_promotion(effects)
    effects.route(E.AFTER_ROLL,"after")
    result,=engine.run(state,(Event(E.ROLL,roll_id=1),Event(E.ACTIVATE_BUILDING,1,roll_id=1,die_index=0,payload=(("trigger","die"),("face",1))),
                            Event(E.AFTER_ROLL,roll_id=1),Event(E.MOVE_BEGIN,payload=(("steps",1),))))
    print("Artificial scripted effects; explicitly supplied order/progress assumptions")
    for entry in result.events:print(entry.describe())
    print("exactness:",registry.exactness)
    print("wallet:",result.state.wallet,"piggy XP:",result.state.building(1).xp)


if __name__=="__main__":run()
