# AGENTS.md

This repository implements an optimizer for Astral Party's solo mode "Astral Town".

Before making any non-trivial change, read:

- `SPEC.md`
- `RULE_STATUS.md`
- `TARGETS.md`

These files are authoritative for the project.

## Core principles

1. Never invent an unknown game rule.
2. Never silently convert a legacy value into a current value.
3. Keep game logic independent from the GUI.
4. Keep gameplay constants and uncertain values data-driven.
5. Represent randomness explicitly in the exact solver.
6. Add regression tests for every implemented game interaction.
7. Prefer deterministic, reproducible simulations.
8. Implement and verify the core engine before GUI work.
9. Do not report completion until the relevant tests and a runnable sample have been executed.
10. If a specification is uncertain, preserve that uncertainty in code and UI rather than guessing.

## Rule confidence

Every gameplay rule/value must carry one of:

- `verified_current`
- `community_current`
- `confirmed_legacy`
- `inferred`
- `unknown`

Definitions are in `RULE_STATUS.md`.

When the solver depends on an `unknown` rule or an `inferred` probability, it must not present the result as an exact optimum unless the user has explicitly supplied an assumption for that rule.

## Source precedence

When sources disagree, use this priority unless a more direct in-game observation is available:

1. Current in-game display or reproducible current-version observation
2. Current Japanese Astral Town wiki / current-version community verification
3. Post-May-21-2026 verification or guides
4. Official patch notes
5. February-2026 legacy wiki / legacy guides
6. Inference

A concrete official numeric value overrides lower-priority sources.

## Architecture rules

The codebase should be layered approximately as:

```text
src/astral_town/
├── model/
├── rules/
├── solver/
├── data/
└── ui/
```

### Model

Contains immutable or effectively immutable domain objects:

- `GameState`
- `BuildingInstance`
- `StandInstance`
- board/space definitions
- enums and event structures

### Rules

Contains all gameplay transitions and effect resolution.

The rules layer must not import PySide6 or any UI module.

### Solver

Contains:

- exact chance-node enumeration
- Expectimax
- management-state search
- transposition/canonicalization
- MCTS / Monte Carlo rollout
- evaluation / risk metrics

The solver may depend on `model` and `rules`, not on the GUI.

### Data

Gameplay constants must be loadable from data files such as YAML or JSON.

Do not hard-code uncertain values deep inside effect implementations.

### UI

PySide6 UI only.

The UI should edit/visualize model state and invoke the solver; it must not own gameplay rules.

## Event engine

Do not implement an entire turn as one large nested `if` chain.

Use an event queue / structured event dispatch system.

At minimum support:

```text
TURN_START

MANAGEMENT_START
BUY_BUILDING
SELL_BUILDING
MERGE_BUILDING
PLACE_BUILDING
MOVE_BUILDING
UNLOCK_LAND
SHOP_REFRESH
MANAGEMENT_END

PRE_ROLL
ROLL
DIE_FACE
ROLL_CONDITION
AFTER_ROLL

MOVE_BEGIN
PASS_BUILDING
PASS_START
FORCED_STOP
MOVE_END

ON_STAY_BUILDING
LAND_SPECIAL_TILE

TURN_END

STAGE_CLEAR
STAND_SELECTION
GAME_CLEAR
GAME_OVER
```

Events should retain enough provenance for debugging, including:

- source object
- activation cause
- roll id
- die index where relevant

## Movement

Movement must be processed one space at a time.

Never replace path traversal with only:

```python
position = (position + movement) % board_size
```

because pass effects and forced stops must resolve during movement.

## Randomness

For exact/expectation calculations, random effects must return weighted outcomes rather than sample immediately.

Conceptually:

```python
list[WeightedOutcome]
```

Use sampling only in Monte Carlo / MCTS paths.

All stochastic simulation paths must support deterministic seeding.

## Natural vs forced activation

Natural die triggers and forced `DICE_EFFECT` activation are distinct concepts.

Use an explicit activation cause, e.g.:

```python
class ActivationCause(Enum):
    NATURAL_DIE = auto()
    FORCED_DICE_EFFECT = auto()
    NATURAL_STAY = auto()
    TRIGGERED_STAY = auto()
```

Do not emulate a forced effect by fabricating a natural die result.

## Recursive effect protection

Effects such as Hall of Wealth can trigger other dice effects.

Use an activation-chain guard so that accidental infinite recursion cannot occur while still allowing legitimate repeated activations from different sources.

A useful key is:

```python
ActivationKey(
    roll_id,
    source_instance_id,
    effect_id,
)
```

## State hashing

`GameState` should be hashable or have a canonical hashable representation.

Transposition tables are required.

Instance ids alone must not prevent equivalent states from canonicalizing to the same solver state.

## Testing

Run tests after each phase.

At minimum:

```bash
pytest
```

Where practical also run a deterministic CLI simulation that prints the event trace.

Do not leave known failing tests in the repository unless they are explicitly marked as expected failures for an unresolved rule.

## Documentation

Keep these current:

- `SPEC.md`
- `RULE_STATUS.md`
- `TARGETS.md`
- `README.md`

When a rule is verified in-game, update `RULE_STATUS.md` and the corresponding data value together.

When a formerly unknown rule becomes known, add a regression test.
