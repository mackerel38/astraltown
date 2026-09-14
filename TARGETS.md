# TARGETS.md

# Implementation Targets

Implement in phases.

Do not begin with GUI polish.

The core engine must be testable from CLI before solver/UI integration.

## Implementation status — 2026-09-14

The original targets below remain requirements. Implemented coverage is summarized here;
this table is not a declaration that the current-game global completion criteria have been met.

| Phase | Implemented and exercised | Remaining boundary |
|---|---|---|
| 0 | Python package, optional Qt dependency, JSON/YAML loader, pytest, CLI | None for bootstrap. |
| 1 | Immutable state, enums, board, events, rational outcomes, serialization, confidence registry, canonicalization | Unknown rules remain null/unresolved. |
| 2 | Structured event queue, full before/after traces, economy, XP, placements, bonuses, sale/merge, charges, modifiers | Uncertain transfer/order rules require explicit configuration. |
| 3 | Ordered dice enumeration, trigger separation, stepwise traversal, Start/Anchor stops, card/shop chances | Actual current topology and modifier consumption are not verified. |
| 4 | All named Prosperity buildings/stands and activation-chain guard | Unspecified forced behaviors and random/ordering policies remain unresolved. |
| 5 | All named Promotion buildings, sale observers, configurable Pig/Palunan framework | Disputed stand values and Fox distributions/sampling require input. |
| 6 | All named Luck buildings/stands, natural vs forced separation | Growth timing, absorbed XP semantics, unknown reward distributions require input. |
| 7 | All named Pirate buildings/stands, Treasure decay/Shovel/Captain ordering | Minimum, generated state, and random-target policies require input. |
| 8 | Common stands, configurable score components and scope/rounding | Current final scoring details remain unresolved; no complete legacy-game profile is claimed. |
| 9 | Exact distributions shared with seeded sampling; independent reward/shop/stand interfaces | Unsupported/missing distributions stop calculation. |
| 10 | Management actions, bounded fixed-plan BFS, canonical deduplication, safe opt-in wallet-dominance helper | Fixed-plan BFS stops at stochastic decisions; Expectimax handles their contingent continuations. Dominance is not enabled without monotonicity. |
| 11 | Expectimax, rational metrics, transpositions, budgets, heuristic API, constrained-policy frontiers | Action/horizon limits are reported; contingent constrained continuations are not yet rendered as full policy trees. |
| 12 | Seeded policy rollout, presets, iteration/time limits, cancellation, confidence intervals | Not MCTS; default continuation is roll / first stand, explicitly reported. |
| 13 | Structured missing-rule IDs, assumption tracking, empirical tracking, no implicit uniform fallback in strict mode | These diagnostics cannot replace real-game verification. |
| 14 | Optional PySide6 editor, 16-space view, all state fields, instance tables, settings, worker cancellation, results | Shop/topology/rules use JSON editors; visual/manual QA used the offscreen Qt backend. |
| 15 | JSON/CSV observations, empirical frequencies/errors/intervals, context-checked explicit import | No true current probabilities inferred from artificial observations. |
| 16 | Profiling, bounded turn-outcome cache preserving identity and rule dependencies | Measured on the supplied artificial scenarios, not an unrestricted full-game benchmark. |

Validation commands and measured examples are recorded in `docs/VALIDATION.md`.
Actual current-version topology, quotas, shop/card/stand data, disputed effects, and scoring still need evidence.
The complete optimizer is **not** declared finished solely because the artificial scenarios run successfully.

## Review corrections and playable profile — 2026-09-14

- SELECT_STAND is a mandatory transition decision, free of ordinary management depth in Expectimax, constrained frontiers, displayed sequences, and the BFS helper.
- SearchBudgetExceeded separates resource exhaustion from missing game rules; only fully evaluated root candidates may survive as bounded search.
- Duplicate stand rejection raises IllegalAction and leaves legal alternatives searchable.
- Palunan sale scope supports total/base_only, retaining unknown confidence and independent score settings.
- Rollout max_rolls counts total calls per trajectory including the first action; incomplete trajectories are not scored.
- Opt-in playable-defaults provides dynamic rational card/reward/shop/stand strategies, uniform targeting, fresh templates, and the explicitly documented legacy/default economy assumptions.
- CLI/GUI rule modes are separate from solver algorithm; used assumptions and their values are reported without changing Rule Status confidence.
- Python 3.12/3.13 core CI and a separate offscreen Python 3.12 GUI smoke job are configured.
- Regression tests cover distributions, hybrid eligibility, confidence/override precedence, strict blockers, cache provenance, GUI modes and all listed review bugs.

Remaining boundaries: non-probability unknowns still require explicit input; full transition enumeration can be expensive;
rollout stand continuation remains first-offer policy (greedy deferred, not MCTS); constrained policy-tree rendering remains partial.
See docs/VALIDATION.md for actually executed checks and current results.

---

# Phase 0 — Repository bootstrap

## Goals

- Create Python 3.12+ package
- Add `pyproject.toml`
- Add `pytest`
- Add type checking if desired
- Add data loader for YAML/JSON
- Create module skeleton
- Add README run instructions

## Exit criteria

- package imports successfully
- `pytest` runs
- a minimal config file loads
- no PySide6 dependency is required for core tests

---

# Phase 1 — Data model and rule-status infrastructure

## Implement

- enums:
  - Pack
  - BuildingType
  - StandType
  - EventType
  - ActivationCause
  - TriggerCardinality
  - RuleConfidence
- `GameState`
- `BuildingInstance`
- `StandInstance`
- `ForcedDieEffect`
- board model
- event model
- weighted outcomes
- immutable/canonical state representation
- rule status registry
- YAML/JSON game-data loading

## Requirements

Every configurable gameplay value should be able to carry:

```text
verified_current
community_current
confirmed_legacy
inferred
unknown
```

## Tests

- state hashing
- serialization round trip
- rule status load
- canonicalization for trivially equivalent states

## Exit criteria

- model is importable with no GUI dependency
- state can be created from config
- uncertain values can be represented as unknown

---

# Phase 2 — Deterministic event engine

## Implement

Event queue and trace logging.

Minimum events:

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

## Implement deterministic actions

- gain/spend coin
- gain XP
- level up
- permanent bonuses
- add/remove building
- place/unplace/move building
- sell
- merge
- stand charges
- forced-stop state
- future-die modifiers

## Tests

- wallet spending does not reduce `stage_progress`
- XP thresholds
- Lv4 max behavior
- deterministic event order
- deterministic trace replay

## Exit criteria

A scripted sequence can be run from CLI and produces a readable trace.

---

# Phase 3 — Dice and movement

## Implement

- one die
- two dice
- exact ordered-pair probabilities
- per-die vs per-roll triggers
- forced die effects
- step-by-step movement
- start forced stop
- Anchor forced stop
- special tile landing
- pass events
- stop events

## Tests

- one-die probabilities sum to 1
- two-die probabilities sum to 1
- movement processes intermediate spaces
- start forced stop discards remaining movement
- Anchor forced stop discards remaining movement
- Anchor 4 priority over Fried Shrimp 6
- two-dice semantics preserve per-die triggers

## Exit criteria

A deterministic die outcome fully resolves movement and movement-triggered events.

---

# Phase 4 — Prosperity effects

## Implement buildings

- Small Wallet
- Wishing Well
- Money Tree
- Lucky Color Gate
- Hall of Wealth
- Rabbit Inn

## Implement stands

- Mimi
- Rabbit
- Raccoon
- Update

## Tests

At minimum:

```text
Small Wallet Lv1 AFTER_ROLL +1

Wishing Well stage-clear permanent +1

Money Tree stay strengthens only adjacent Prosperity buildings

Lucky Color Gate uses correct pack-count side

Hall of Wealth natural 3/4 activates adjacent Prosperity effects

two triggering dice still cause only one Hall activation

Hall forced effect does not create recursion loop

two Halls can legitimately cause repeated activation of another building

Rabbit Inn pass payout works

Rabbit Inn own strengthening does not select itself

start-shop opening charges Update Stand
```

## Exit criteria

All Prosperity tests pass.

---

# Phase 5 — Promotion effects

## Implement buildings

- Piggy Bank
- Piglet Bank
- Small Bookstore
- Beckoning Cat Vault
- Fox Antique Shop

## Implement stand framework

- Pig Stand configurable threshold
- Palunan configurable multipliers/rounding

Do not choose disputed current values by default.

## Tests

```text
Piggy natural 1 -> +2 coin +2 XP

Piggy sell bonus by level

Piglet AFTER_ROLL XP

Small Bookstore current values, not legacy values

Beckoning Cat Vault reacts to each Piggy/Piglet sale

multiple Vaults independently observe sale

Fox natural 5 XP behavior by level

Fox pass produces a chance node, not a sampled result in exact mode
```

## Exit criteria

Promotion buildings work with unknown stand settings preserved.

---

# Phase 6 — Luck effects

## Implement buildings

- Dice Sculpture
- Four-leaf Inn
- Lucky Star Coin Pond
- Dice Tower
- Hologram Experience Hut

## Implement stands

- Jasmine
- Fried Shrimp
- Three-leaf

## Tests

```text
two even dice -> Four-leaf payout twice

natural 6 -> Four-leaf permanent growth

forced Four-leaf DICE_EFFECT -> payout but no natural-6 growth

Pond natural 1 -> next action uses two dice

Pond forced effect can enable two dice

Dice Tower natural 4 removes one random Dice Sculpture

Dice Tower natural 6 payout

two-dice 4 + 6 can trigger both Dice Tower branches

forced Dice Tower DICE_EFFECT uses absorption branch

Hologram payout uses sum of two dice

Jasmine charge threshold

Fried Shrimp future 6

Three-leaf natural-6 charge is per die
```

## Exit criteria

All Luck tests pass.

---

# Phase 7 — Pirate effects

## Implement buildings

- Treasure
- Sail
- Rudder
- Anchor
- Cannon
- Captain Hat

## Implement stands

- Pirate King
- Great Shark
- Shovel
- Small Shark

## Tests

```text
Treasure Lv1 initial stay payout 12

each Treasure stay activation increments decay

triggered Treasure stay also increments decay

Treasure minimum uses configured rule

fresh Treasure target can reset old Treasure decay on merge

Sail pass/stay/die-4 payouts

Rudder pass triggers one random Treasure stay

Rudder stay activates random Luck DICE_EFFECT

Anchor pass stops movement and sets future 4

Cannon natural 4 triggers adjacent Treasure/Sail stay

Cannon pass grants Treasure and payout

Captain Hat triggers Treasure stays before removal

Captain Hat permanent pass bonus accumulates

Pirate King changes pass/stay bonuses only

Great Shark threshold triggers all Treasure/Sail stays

every Treasure stay activation charges Shovel

Shovel threshold pays 88

Small Shark start pass payout equals placed Pirate count
```

## Exit criteria

All Pirate tests pass.

---

# Phase 8 — Common stands and scoring

## Implement stands

- Big Bag
- Roller
- Secret Book
- Credit Card

## Implement score

```text
progress_score
star_coin_score
building_score
```

with configurable unknown rounding/scope behavior.

## Tests

```text
Credit Card = floor(wallet / 50)

Secret Book may select Lv4

Big Bag exact mode creates random-copy chance outcomes

score current-mode uses configured placed-building scope

wallet half rounding is controlled by config
```

## Exit criteria

Current/legacy scoring modes can be selected without code changes.

---

# Phase 9 — Random outcome API

## Implement

All random rules as explicit distributions:

- random target
- random generated building
- card tile
- shop
- stand offer
- Big Bag
- Fox reward
- Three-leaf reward

Suggested API:

```python
list[WeightedOutcome]
```

Exact solver paths must not call RNG.

Monte Carlo paths may sample from the same distribution definitions.

## Tests

For every chance node:

```text
probability sum == 1
no impossible state emitted
unknown distribution raises/returns unresolved status in strict mode
```

## Exit criteria

Rules engine can be used either in exact or sampled mode.

---

# Phase 10 — Management actions

## Implement

```text
BUY
SELL
MERGE
PLACE
MOVE_BUILDING
UNLOCK_LAND
REFRESH_SHOP
END_MANAGEMENT_AND_ROLL
SELECT_STAND
```

Build management-state search.

Use:

- BFS or beam search
- canonical state deduplication
- dominance pruning where safe

## Tests

```text
different action orders leading to equivalent state canonicalize together

sell-trigger counters are preserved

shop state differences prevent invalid dominance

stage progress differences prevent invalid dominance

wallet-dominated identical states can be pruned where safe
```

## Exit criteria

Given a state before rolling, enumerate reasonable candidate management plans ending in roll.

---

# Phase 11 — Expectimax

## Implement

- decision nodes
- chance nodes
- horizon control
- transposition table
- exact dice enumeration
- exact random-target enumeration where distributions are known
- configurable heuristic at cutoff

## Output

At least:

```text
best action / management plan
EV
P(clear)
second-best difference
exactness status
```

## Tests

Create small artificial states with hand-computable expectations.

Verify:

- action selection
- chance weighting
- transposition reuse
- exact rational expectation where practical

## Exit criteria

A small state can be solved exactly for multiple future rolls.

---

# Phase 12 — Long-horizon search

## Implement one or more

- MCTS
- Monte Carlo rollout
- beam-search rollout

Recommended hybrid:

```text
near horizon:
Expectimax

far horizon:
Monte Carlo / MCTS
```

## Requirements

- deterministic seed option
- iteration/time budget
- stop/cancel support
- confidence interval
- exactness/sampling label

## Presets

```text
FAST
NORMAL
DEEP
VERY_DEEP
```

Do not rely on fixed wall-clock timing in tests; expose iteration limits too.

## Tests

```text
same seed + same iteration count -> reproducible result

more rollouts do not corrupt state

cancel terminates cleanly

confidence interval is reported for sampled estimates
```

## Exit criteria

A realistic state returns recommendations within configurable compute budget.

---

# Phase 13 — Strict exact mode / uncertainty handling

## Implement

When an unresolved rule is required:

```text
Exact calculation cannot proceed.
```

Return a structured list of missing rule ids.

Do not silently substitute uniform probabilities.

Allow user-provided assumptions.

## Tests

```text
unknown card distribution blocks strict exact path

supplying card distribution unblocks calculation

unknown rules not touched by current state do not block unrelated exact analysis
```

## Exit criteria

Exactness claims are always defensible.

---

# Phase 14 — PySide6 GUI

Only begin after the engine and solver are usable from CLI.

## Game State panel

Editable:

- difficulty
- stage
- turns remaining
- wallet
- stage progress
- position
- selected packs

## Board

Render 16-space ring.

For each building:

- type
- level
- XP
- dice bonus
- pass bonus
- stay bonus
- counters

## Inventory

Edit unplaced buildings.

## Stands

Edit stand ownership and charges.

## Shop

Edit current offers.

## Solver panel

Controls:

- objective
- clear threshold
- risk lambda
- compute budget
- strict exact toggle
- calculate
- stop

Results:

- top 3 plans
- EV
- P(clear)
- confidence/exactness
- next-best gap

## Rule Status panel

Show:

```text
verified_current
community_current
confirmed_legacy
inferred
unknown
```

Also show exact-solver blockers.

## Exit criteria

A complete state can be entered manually and solved without touching code.

---

# Phase 15 — Empirical calibration

## Implement

Observation import/export for unknown probabilities.

At least CSV or JSON.

Compute:

- sample count
- empirical frequency
- standard error
- 95% confidence interval

Possible data:

- shop offers
- card tile rewards
- stand offers
- random target selection

## Requirements

Empirical estimates must remain labeled empirical.

Do not mutate `verified_current` status merely because a sample is large.

## Exit criteria

The user can collect game observations and plug them into solver distributions.

---

# Phase 16 — Performance

## Optimize after correctness

Potential techniques:

- transposition tables
- canonical instance ordering
- compact immutable state
- memoized deterministic transitions
- chance-node aggregation
- beam pruning
- action dominance
- multiprocessing only if architecture remains deterministic/testable

Profile before micro-optimizing.

## Exit criteria

Normal preset is usable on realistic states.

---

# Mandatory regression tests

These are required regardless of phase organization:

```text
1. Buying decreases wallet but not stage_progress.

2. Small Wallet Lv1 gives +1 after roll.

3. Wishing Well permanently gains +1 at stage clear.

4. Two even dice trigger Four-leaf Inn twice.

5. Dice 3 and 4 still trigger a Hall of Wealth only once per roll.

6. Forced Four-leaf DICE_EFFECT does not perform natural-6 permanent growth.

7. Forced Dice Tower DICE_EFFECT uses the absorption branch.

8. Anchor pass discards remaining movement.

9. Anchor forced 4 has priority over Fried Shrimp forced 6.

10. Captain Hat activates all Treasure stays before removing them.

11. Every Treasure stay activation charges Shovel.

12. Every Treasure stay activation advances Treasure decay.

13. Merging old decayed Treasure into a fresh target does not copy decay.

14. Pirate King strengthens pass/stay coin amounts, not arbitrary die payouts.

15. Credit Card payout equals floor(wallet / 50).

16. Opening shop from start forced-stop charges Update Stand.

17. Lucky Color Gate is ineligible without both Prosperity and Luck packs.

18. Rudder is ineligible without both Luck and Pirate packs.

19. Every exact chance node has probability sum 1.

20. Fixed random seed reproduces sampled simulations.

21. Current scoring mode can restrict building score to placed buildings.

22. Unknown rules are never silently filled in during strict exact mode.
```

---

# Completion criteria

The project is complete only when all of the following hold:

```text
pytest passes

all currently specified buildings are implemented

all currently specified stands are implemented

unknown rules are not silently guessed

event trace can explain one full turn

same seed reproduces sampled execution

arbitrary GameState can be entered in GUI

solver returns top 3 plans from a current state

each plan includes EV and clear probability

near-horizon chance nodes are exactly enumerated when their rules are known

long-horizon estimation supports MCTS/Monte Carlo or equivalent

calculation can be stopped

gameplay values can be edited without code changes

README is sufficient to run the application

RULE_STATUS.md lists known/legacy/inferred/unknown rules

legacy and current values are not mixed

at least one realistic sample state has been solved end-to-end after implementation
```

Do not report the project as finished before these checks are actually performed.
