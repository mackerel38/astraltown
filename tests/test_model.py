import json
from dataclasses import replace
from fractions import Fraction

import pytest

from astral_town.model.board import Board, Lot, Space
from astral_town.model.enums import RuleConfidence, SpaceType
from astral_town.model.outcomes import WeightedOutcome, validate_distribution
from astral_town.model.serialization import decode, encode
from astral_town.rules.registry import RuleRegistry, UnresolvedRule
from astral_town.samples import model_sample


def test_state_hash_and_round_trip():
    state = model_sample()
    restored = decode(json.loads(json.dumps(encode(state))))
    assert restored == state
    assert hash(restored) == hash(state)
    assert state in {restored}


def test_canonical_ignores_identity_but_not_counters():
    state = model_sample()
    renamed = replace(state, buildings=(replace(state.buildings[0], instance_id=55),),
                      inventory=(replace(state.inventory[0], instance_id=66),))
    assert state != renamed
    assert state.canonical_key() == renamed.canonical_key()
    changed = renamed.with_building(replace(renamed.buildings[0], pass_coin_bonus=1))
    assert changed.canonical_key() != state.canonical_key()
    assert replace(state, stage_progress=1).canonical_key() != state.canonical_key()


def test_invalid_placement():
    with pytest.raises(ValueError):
        replace(model_sample(), unlocked_lots=frozenset())


def test_rule_confidence_and_unknown():
    registry = RuleRegistry.builtin()
    assert registry.require("board_size") == 16
    assert registry.values["initial_wallet"].value is None
    with pytest.raises(UnresolvedRule) as exc:
        registry.require("initial_wallet")
    assert exc.value.rule_ids == ("initial_wallet",)


@pytest.mark.parametrize("status", ["unknown", "inferred", "confirmed_legacy"])
def test_no_implicit_fallback(status):
    data = {"version": "test", "rules": {"x": {"value": 8, "confidence": status, "source": "fixture"}}}
    with pytest.raises(UnresolvedRule):
        RuleRegistry.from_data(data).require("x")
    configured = RuleRegistry.from_data(data, {"x": 12})
    assert configured.require("x") == 12
    assert configured.exactness == "assumption-based"


def test_board_round_trip_and_validation():
    board = Board((Space(0, SpaceType.START), Space(1, SpaceType.NORMAL, 3)),
                  (Lot(3, frozenset()),), RuleConfidence.INFERRED, "artificial fixture")
    assert decode(encode(board)) == board
    assert board.next_space(1).id == 0
    with pytest.raises(ValueError):
        replace(board, lots=(Lot(3, frozenset({7})),))


def test_exact_probability():
    state = model_sample()
    outcomes = (WeightedOutcome(Fraction(1, 3), state), WeightedOutcome(Fraction(2, 3), state))
    assert validate_distribution(outcomes) == outcomes
    assert decode(encode(outcomes)) == outcomes
    with pytest.raises(ValueError):
        validate_distribution(outcomes[:1])
    with pytest.raises(ValueError):
        WeightedOutcome(0.5, state)
