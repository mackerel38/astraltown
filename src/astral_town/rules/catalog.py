from astral_town.model.enums import Pack


def required_packs(building_type, registry):
    return frozenset(Pack(p) for p in registry.require(f"{building_type.value}.packs"))


def eligible(building_type, selected_packs, registry):
    return required_packs(building_type, registry) <= selected_packs


def sell_value(building, registry):
    rarity = registry.require(f"{building.building_type.value}.rarity")
    base = registry.require("sell_values")[rarity][building.level - 1]
    key = f"{building.building_type.value}.sell"
    bonus = registry.require(key)[building.level - 1] if key in registry.values else 0
    return base + bonus
