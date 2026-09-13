from astral_town.model.enums import Pack


def stand_eligible(kind,packs,registry):
    return frozenset(Pack(p) for p in registry.require(f"{kind.value}.packs"))<=packs
