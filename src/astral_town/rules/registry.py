"""Rule resolution never substitutes legacy values or inferred probabilities."""

from dataclasses import dataclass
from types import MappingProxyType

from astral_town.data.loader import load_builtin
from astral_town.model.enums import RuleConfidence


class UnresolvedRule(Exception):
    def __init__(self, *rule_ids):
        self.rule_ids = tuple(sorted(set(rule_ids)))
        super().__init__("Required unresolved rules: " + ", ".join(self.rule_ids))


def freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(freeze(v) for v in value)
    return value


@dataclass(frozen=True)
class RuleValue:
    value: object
    confidence: RuleConfidence
    source: str

    def __post_init__(self):
        object.__setattr__(self, "value", freeze(self.value))
        if not self.source:
            raise ValueError("Rule source is required")


class RuleRegistry:
    def __init__(self, version: str, values: dict[str, RuleValue], assumptions=None, *, legacy=False):
        self.version = version
        self.values = MappingProxyType(dict(values))
        self.assumptions = freeze(dict(assumptions or {}))
        self.legacy = legacy
        self.used: set[str] = set()
        self.missing: set[str] = set()
        self.empirical = {}

    @classmethod
    def from_data(cls, data, assumptions=None, *, legacy=False):
        return cls(data["version"], {key: RuleValue(value["value"], RuleConfidence(value["confidence"]), value["source"])
                                     for key, value in data["rules"].items()}, assumptions, legacy=legacy)

    @classmethod
    def builtin(cls, assumptions=None, *, legacy=False):
        return cls.from_data(load_builtin(), assumptions, legacy=legacy)

    def require(self, key):
        self.used.add(key)
        if key in self.assumptions and self.assumptions[key] is not None:
            return self.assumptions[key]
        rule = self.values.get(key)
        if rule is None or rule.value is None:
            self.missing.add(key)
            raise UnresolvedRule(key)
        allowed = {RuleConfidence.VERIFIED_CURRENT, RuleConfidence.COMMUNITY_CURRENT}
        if self.legacy:
            allowed.add(RuleConfidence.CONFIRMED_LEGACY)
        if rule.confidence not in allowed:
            self.missing.add(key)
            raise UnresolvedRule(key)
        return rule.value

    def distribution(self,key,state):
        if key not in self.empirical:return self.require(key)
        report=self.empirical[key]
        context=report["context"]
        if report.get("method")!="empirical" or report.get("sample_count",0)<1:raise ValueError("Invalid empirical distribution")
        rule=self.values.get(key)
        if rule and rule.confidence==RuleConfidence.VERIFIED_CURRENT:raise ValueError("Empirical estimate cannot override verified_current")
        expected={"stage_index":state.stage_index,"selected_packs":sorted(p.value for p in state.selected_packs),"difficulty_id":state.difficulty_id}
        if any(k not in expected or expected[k]!=(sorted(v) if k=="selected_packs" else v) for k,v in context.items()):raise UnresolvedRule(key+".empirical_context")
        self.used.add(key)
        return freeze(report["distribution"])

    @property
    def exactness(self):
        if self.missing:
            return "unresolved"
        if any(key in self.assumptions or key in self.empirical for key in self.used):
            return "assumption-based"
        if self.legacy:
            return "legacy-model"
        return "exact"
