"""One-step traversal, including pass effects before checking remaining movement."""

from dataclasses import replace

from astral_town.model.enums import ActivationCause, BuildingType as B, EventType as E, RuleConfidence, SpaceType
from astral_town.model.events import Event
from .engine import deterministic
from .registry import UnresolvedRule
from .randomness import configured_distribution
from .engine import Transition
from .economy import add_building
from .catalog import eligible
from astral_town.model.building import BuildingInstance, ShopOffer
from astral_town.model.outcomes import WeightedOutcome
from .rewards import building_from_template,require_reward_capacity


def install_movement(engine, board, *, accept_topology_assumption=False):
    registry = engine.registry
    if board.confidence not in {RuleConfidence.VERIFIED_CURRENT, RuleConfidence.COMMUNITY_CURRENT}:
        if not accept_topology_assumption:
            raise UnresolvedRule("board_topology")

    def move_begin(state, event):
        amount = event.get("steps", sum(state.last_roll))
        if type(amount) is not int or amount < 0:
            raise ValueError("Movement must be a nonnegative integer")
        return deterministic(replace(state, movement_remaining=amount, forced_stop=False),
                             Event(E.MOVE_STEP, roll_id=state.roll_id, payload=(("continue", True),)))

    def move_step_or_end(state, event):
        if not event.get("continue"):
            return deterministic(state)
        if state.movement_remaining > 0 and not state.forced_stop:
            space = board.next_space(state.player_position)
            moved = replace(state, player_position=space.id, movement_remaining=state.movement_remaining - 1)
            building = next((b for b in moved.buildings if b.location == space.lot_id), None)
            next_events = []
            if building:
                next_events.append(Event(E.PASS_BUILDING, building.instance_id, roll_id=state.roll_id))
            if space.type == SpaceType.START:
                next_events.extend((Event(E.PASS_START, roll_id=state.roll_id), Event(E.FORCED_STOP, roll_id=state.roll_id),
                                    Event(E.SHOP_REFRESH, roll_id=state.roll_id, payload=(("reason", "start"),))))
            next_events.append(event)
            return deterministic(moved, *next_events)
        space = next(s for s in board.spaces if s.id == state.player_position)
        building = next((b for b in state.buildings if b.location == space.lot_id), None)
        end = [Event(E.MOVE_END, roll_id=state.roll_id)]
        if building:
            end.append(Event(E.ON_STAY_BUILDING, building.instance_id, ActivationCause.NATURAL_STAY, state.roll_id))
        if space.type in {SpaceType.COIN, SpaceType.CARD}:
            end.append(Event(E.LAND_SPECIAL_TILE, roll_id=state.roll_id, payload=(("tile", space.type.value),)))
        return deterministic(state, *end)

    def pass_building(state, event):
        building = state.building(event.source_id)
        if building.building_type == B.ANCHOR:
            amount = registry.require("anchor_pass")[building.level - 1] + building.pass_coin_bonus
            return deterministic(state, Event(E.GAIN_COIN, building.instance_id, roll_id=state.roll_id,
                                  payload=(("amount", amount), ("progress", "building" in registry.require("gain_progress_sources")))),
                                  Event(E.FORCED_STOP, building.instance_id, roll_id=state.roll_id),
                                  Event(E.SET_FUTURE_DIE, building.instance_id, roll_id=state.roll_id,
                                  payload=(("face", registry.require("anchor_face")), ("priority", registry.require("anchor_priority")), ("source", "ANCHOR"))))
        # Only known no-pass-effect buildings are accepted before effect packs are installed.
        if building.building_type not in {B.SMALL_WALLET, B.WISHING_WELL, B.MONEY_TREE, B.LUCKY_COLOR_GATE,
                                         B.HALL_OF_WEALTH, B.PIGGY_BANK, B.PIGLET_BANK, B.DICE_SCULPTURE,
                                         B.FOUR_LEAF_INN, B.LUCKY_STAR_COIN_POND, B.DICE_TOWER, B.TREASURE}:
            raise NotImplementedError(f"Pass effect not installed: {building.building_type}")
        return deterministic(state)

    def special(state, event):
        if event.get("tile") == SpaceType.COIN.value:
            return deterministic(state, Event(E.GAIN_COIN, roll_id=state.roll_id,
                payload=(("amount", registry.require("coin_tile_payout")),
                         ("progress", "tile" in registry.require("gain_progress_sources")))))
        if event.get("tile") == SpaceType.CARD.value:
            outcomes = configured_distribution(registry, "card_distribution", state)
            require_reward_capacity(state,registry)
            result = []
            for outcome in outcomes:
                building = reward_building(state, outcome.state)
                result.append(WeightedOutcome(outcome.probability, Transition(add_building(state, building, registry))))
            return tuple(result)
        raise ValueError("Unsupported special tile")

    def shop_refresh(state, event):
        if event.get("offers_already_drawn"):
            return deterministic(replace(state,shop_refresh_count=state.shop_refresh_count+1))
        outcomes = configured_distribution(registry, "shop_distribution", state)
        result = []
        for outcome in outcomes:
            offers = tuple(ShopOffer(i, reward_building(state, row["building"], offset=i), row["price"])
                           for i, row in enumerate(outcome.state))
            result.append(WeightedOutcome(outcome.probability, Transition(replace(state, shop_offers=offers,
                                                                                 shop_refresh_count=state.shop_refresh_count + 1))))
        return tuple(result)

    def reward_building(state, row, offset=0):
        return building_from_template(state,row,registry,offset)

    engine.register(E.MOVE_BEGIN, move_begin)
    engine.register(E.MOVE_STEP, move_step_or_end)
    engine.register(E.PASS_BUILDING, pass_building)
    engine.register(E.LAND_SPECIAL_TILE, special)
    engine.register(E.SHOP_REFRESH, shop_refresh)
