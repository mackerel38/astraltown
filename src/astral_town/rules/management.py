from dataclasses import replace

from astral_town.model.enums import EventType as E, StandType
from . import economy
from .catalog import eligible, sell_value
from .engine import deterministic
from .errors import IllegalAction
from .engine import Transition
from .randomness import configured_distribution
from .rewards import building_from_template
from astral_town.model.building import ShopOffer
from astral_town.model.events import Event
from astral_town.model.outcomes import WeightedOutcome


def install_management(engine):
    registry = engine.registry

    def buy(state, event):
        offer = next(o for o in state.shop_offers if o.offer_id == event.get("offer_id"))
        if not eligible(offer.building.building_type, state.selected_packs, registry):
            raise IllegalAction("Offer requires unavailable packs")
        if any(s.stand_type == StandType.PALUNAN for s in state.stands):
            from .effects.promotion import palunan_amount
            price = palunan_amount(offer.price,registry,"palunan_purchase")
        else:
            price = offer.price
        refill = registry.require("shop_refill")
        building=offer.building
        if any(b.instance_id==building.instance_id for b in state.buildings+state.inventory):
            building=replace(building,instance_id=max(b.instance_id for b in state.buildings+state.inventory)+1)
        result = economy.add_building(economy.spend_coin(state, price), building, registry)
        result=replace(result,shop_offers=tuple(o for o in result.shop_offers if o.offer_id!=offer.offer_id))
        if refill=="none":return deterministic(result)
        if refill!="replace_slot":raise ValueError("Supported refill policies: none, replace_slot")
        refresh=registry.require("purchase_refill_counts_as_refresh")
        if type(refresh) is not bool:raise ValueError("purchase_refill_counts_as_refresh must be boolean")
        events=(Event(E.SHOP_REFRESH,payload=(("offers_already_drawn",True),)),) if refresh else ()
        outcomes=[]
        for outcome in configured_distribution(registry,"shop_refill_distribution",result):
            new=ShopOffer(offer.offer_id,building_from_template(result,outcome.state["building"],registry),outcome.state["price"])
            offers=tuple(new if o.offer_id==offer.offer_id else o for o in state.shop_offers)
            outcomes.append(WeightedOutcome(outcome.probability,Transition(replace(result,shop_offers=offers),events)))
        return tuple(outcomes)

    def sell(state, event):
        building = state.building(event.source_id)
        # Observers must be implemented before selling into those states.
        if any(s.stand_type in {StandType.PIG, StandType.PALUNAN} for s in state.stands):
            registry.require("sale_stand_effects")
            raise NotImplementedError("Sale stand observers pending")
        from astral_town.model.enums import BuildingType as B
        if any(b.building_type == B.BECKONING_CAT_VAULT for b in state.buildings):
            raise NotImplementedError("Vault sale observer pending Phase 5")
        progress_sources = registry.require("gain_progress_sources")
        result = economy.gain_coin(economy.remove_building(state, building.instance_id),
                                   sell_value(building, registry), counts_for_progress="sale" in progress_sources)
        return deterministic(result)

    def unlock(state, event):
        lot = event.get("lot")
        if lot in state.unlocked_lots:
            raise IllegalAction("Lot already unlocked")
        price = registry.require("land_prices").get(str(lot))
        if price is None:
            raise IllegalAction("Lot is not available for purchase")
        return deterministic(replace(economy.spend_coin(state, price), unlocked_lots=state.unlocked_lots | {lot}))

    engine.register(E.BUY_BUILDING, buy)
    engine.register(E.SELL_BUILDING, sell)
    engine.register(E.UNLOCK_LAND, unlock)
