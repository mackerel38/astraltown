from dataclasses import dataclass,fields

from .enums import ActivationCause, EventType


@dataclass(frozen=True)
class ActivationKey:
    roll_id: int | None
    source_instance_id: int
    effect_id: str


@dataclass(frozen=True)
class Event:
    type: EventType
    source_id: int | None = None
    cause: ActivationCause | None = None
    roll_id: int | None = None
    die_index: int | None = None
    payload: tuple[tuple[str, object], ...] = ()
    chain: tuple[ActivationKey, ...] = ()

    def __post_init__(self):
        object.__setattr__(self,"payload",tuple(tuple(pair) for pair in self.payload))
        object.__setattr__(self,"chain",tuple(self.chain))
        if len(dict(self.payload))!=len(self.payload):raise ValueError("Duplicate event payload key")

    def get(self, key, default=None):
        return dict(self.payload).get(key, default)


@dataclass(frozen=True)
class EventLogEntry:
    event: Event
    before: "GameState"
    after: "GameState"

    def describe(self) -> str:
        changes=[]
        before={b.instance_id:b for b in self.before.buildings+self.before.inventory}
        after={b.instance_id:b for b in self.after.buildings+self.after.inventory}
        for instance_id in sorted(before.keys()|after.keys()):
            if instance_id not in before:
                b=after[instance_id];changes.append(f"add {b.building_type.value}#{instance_id} Lv{b.level} XP{b.xp} lot={b.location}")
            elif instance_id not in after:changes.append(f"remove {before[instance_id].building_type.value}#{instance_id}")
            else:
                a,b=before[instance_id],after[instance_id]
                for field in fields(a):
                    old,new=getattr(a,field.name),getattr(b,field.name)
                    if old!=new:changes.append(f"{b.building_type.value}#{instance_id}.{field.name}={old}->{new}")
        old_stands={s.instance_id:s for s in self.before.stands}
        for stand in self.after.stands:
            old=old_stands.get(stand.instance_id)
            if old is None:changes.append(f"add stand {stand.stand_type.value}#{stand.instance_id}")
            elif old.charge!=stand.charge:changes.append(f"{stand.stand_type.value}#{stand.instance_id}.charge={old.charge}->{stand.charge}")
        for name in ("player_position","last_roll","turns_remaining","stage_index","progress_score","next_dice_count","forced_die_effects","forced_stop","shop_refresh_count","phase","status"):
            old,new=getattr(self.before,name),getattr(self.after,name)
            if old!=new:changes.append(f"{name}={old}->{new}")
        return (f"{self.event.type.value} source={self.event.source_id} "
                f"cause={self.event.cause} roll={self.event.roll_id} die={self.event.die_index} "
                f"wallet={self.before.wallet}->{self.after.wallet} "
                f"progress={self.before.stage_progress}->{self.after.stage_progress} "
                f"payload={dict(self.event.payload)}"+(" | "+"; ".join(changes) if changes else ""))


from .state import GameState
