# SPEC.md

# Astral Town Optimizer Specification

## 1. Goal

Implement a local application for Astral Party's solo mode "Astral Town" that accepts a current game state and recommends actions maximizing expected final score.

Primary objective:

\[
\max_\pi \mathbb{E}[\mathrm{FinalScore}\mid s,\pi]
\]

The application is not merely a simulator. It must include:

1. A rules engine reproducing Astral Town state transitions
2. Explicit probability handling
3. Management decision search
4. Dice / movement / building / stand resolution
5. Expected-value and clear-probability analysis
6. A GUI for manual state entry
7. Data-driven handling of uncertain rules
8. Traceable and reproducible simulations

## 2. Solver objectives

Support at least these modes:

```text
EXPECTED_SCORE
CLEAR_PROBABILITY
EXPECTED_SCORE_WITH_CLEAR_CONSTRAINT
RISK_ADJUSTED_SCORE
```

For constrained expected score:

```text
P(clear) >= user_threshold
```

For risk-adjusted score, a default form may be:

```text
E[score] - lambda * P(fail)
```

Solver output should include:

- recommended action sequence
- expected final score
- clear probability
- expected final wallet
- expected building score
- expected progress score
- Monte Carlo confidence interval when applicable
- difference versus the next-best action
- whether the result is exact, assumption-based, or simulation-estimated

## 3. Recommended project layout

```text
astral-town-optimizer/
├── pyproject.toml
├── README.md
├── AGENTS.md
├── SPEC.md
├── RULE_STATUS.md
├── TARGETS.md
├── src/
│   └── astral_town/
│       ├── model/
│       │   ├── state.py
│       │   ├── building.py
│       │   ├── stand.py
│       │   ├── board.py
│       │   └── events.py
│       ├── rules/
│       │   ├── engine.py
│       │   ├── movement.py
│       │   ├── dice.py
│       │   ├── economy.py
│       │   └── effects/
│       │       ├── common.py
│       │       ├── prosperity.py
│       │       ├── promotion.py
│       │       ├── luck.py
│       │       └── pirate.py
│       ├── solver/
│       │   ├── expectimax.py
│       │   ├── management_search.py
│       │   ├── mcts.py
│       │   ├── transposition.py
│       │   └── evaluation.py
│       ├── data/
│       │   ├── buildings.yaml
│       │   ├── stands.yaml
│       │   ├── difficulties.yaml
│       │   ├── board.yaml
│       │   ├── shop.yaml
│       │   └── rule_status.yaml
│       └── ui/
│           ├── app.py
│           └── widgets/
└── tests/
```

Python 3.12+.

Use PySide6 for GUI.

## 4. Core state

Use an immutable or canonicalizable state.

A baseline model:

```python
@dataclass(frozen=True)
class GameState:
    difficulty_id: str

    stage_index: int
    turns_remaining: int

    wallet: int
    stage_progress: int

    player_position: int

    selected_packs: frozenset[Pack]

    unlocked_lots: frozenset[int]
    buildings: tuple[BuildingInstance, ...]
    inventory: tuple[BuildingInstance, ...]

    stands: tuple[StandInstance, ...]

    shop_offers: tuple[ShopOffer, ...]
    shop_refresh_count: int

    next_dice_count: int
    forced_die_effects: tuple[ForcedDieEffect, ...]

    rule_version: str
```

`wallet` and `stage_progress` must be separate.

Spending coins must not reduce already-earned stage progress.

## 5. Building instance state

Building type alone is insufficient.

Suggested model:

```python
@dataclass(frozen=True)
class BuildingInstance:
    instance_id: int
    building_type: BuildingType

    level: int
    xp: int

    location: int | None

    dice_coin_bonus: int = 0
    pass_coin_bonus: int = 0
    stay_coin_bonus: int = 0

    wish_stage_bonus: int = 0
    treasure_decay: int = 0
    captain_pass_bonus: int = 0

    custom_counters: tuple[tuple[str, int], ...] = ()
```

Do not collapse `dice_coin_bonus`, `pass_coin_bonus`, and `stay_coin_bonus` into one value.

## 6. Packs

Current pack categories:

```text
PROSPERITY = 財宝
PROMOTION  = 昇進
LUCK       = 幸運
PIRATE     = 海賊
```

Selected packs restrict the buildings and stands that may appear.

Hybrid buildings require all required packs.

Known hybrid requirements:

```text
幸運の彩り門: {PROSPERITY, LUCK}
舵:           {LUCK, PIRATE}
```

Eligibility rule:

```python
building.required_packs <= state.selected_packs
```

## 7. Board

Known current properties:

- 16 spaces per circuit
- stopping on a yellow coin tile gives 5 coins
- stopping on a green card tile gives a random building
- passing the blue start tile causes forced stop
- a shop opens after the start forced stop
- coin and card tiles appear at intervals of four spaces
- physical lot adjacency counts across a corner
- opening a shop due to start forced-stop also counts as a shop refresh for Update Stand

Do not hard-code exact lot/space mapping until verified.

Use `board.yaml`.

Example structure:

```yaml
spaces:
  - id: 0
    type: START

lots:
  - id: 0
    adjacent_lots: []
    corresponding_special_tile: null
```

## 8. Initial state

Current confirmed starting buildings:

```text
小さな財布
貯金箱
賽の目彫刻
```

They are initially owned, not necessarily placed.

Legacy-only initial values are kept in `RULE_STATUS.md`, not promoted to current defaults without explicit configuration.

## 9. Dice

Normal action:

- one fair six-sided die
- results 1 through 6

Two-dice mode:

- movement uses the sum of both dice
- effects may inspect each die separately

Exact probability:

```text
ordered pair: 1/36 each
```

Equivalent outcomes may be compressed only when no rule distinguishes them.

### Trigger cardinality

Every die-trigger effect should declare whether it triggers:

```text
PER_DIE
PER_ROLL
```

Examples:

- Four-leaf Inn: per die
- Hall of Wealth: once per roll even if both dice are 3/4
- Dice Tower: separate 4-side and 6-side conditions may both occur in one two-die roll

## 10. Forced die effects

Known effects:

### Fried Shrimp Stand

Natural die result 1:

```text
next die = 6
```

### Anchor

Passing Anchor:

```text
forced stop
next die = 4
```

Anchor's forced 4 has higher priority than Fried Shrimp's forced 6.

Suggested representation:

```python
@dataclass(frozen=True)
class ForcedDieEffect:
    face: int
    priority: int
    source: str
```

Known priority relation:

```text
ANCHOR_4 > FRIED_SHRIMP_6
```

Two-dice interaction:

- current evidence indicates Anchor can fix one die at 4 while the other remains random

Unknown details such as effect consumption/persistence must remain configurable.

## 11. Level / XP

Current known XP thresholds:

| Level | XP to next | cumulative |
|---|---:|---:|
| 1 | 5 | 0 |
| 2 | 10 | 5 |
| 3 | 15 | 15 |
| 4 | MAX | 30 |

Lv4 cannot be used as merge material.

Base merge XP from using the same building is currently treated as 5 under community-current evidence.

Transfer of pre-existing source XP remains unresolved and must be configurable.

## 12. Rarity and sell value

Community-current sell values:

| Rarity | Lv1 | Lv2 | Lv3 | Lv4 |
|---|---:|---:|---:|---:|
| Green | 4 | 8 | 12 | 16 |
| Blue | 8 | 16 | 24 | 32 |
| Purple | 15 | 30 | 45 | 60 |
| Gold | 25 | 50 | 75 | 100 |

Legacy purchase prices:

```text
Green  8
Blue   16
Purple 30
Gold   50
```

Only use legacy purchase prices when explicitly enabled or when confirmed.

## 13. Event model

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

Example event structure:

```python
@dataclass(frozen=True)
class Event:
    type: EventType
    source_id: int | None
    cause: ActivationCause | None
    roll_id: int | None
    die_index: int | None
```

## 14. Activation causes

Use explicit causes:

```python
class ActivationCause(Enum):
    NATURAL_DIE = auto()
    FORCED_DICE_EFFECT = auto()
    NATURAL_STAY = auto()
    TRIGGERED_STAY = auto()
```

This is critical because forced dice-effect activation can differ from natural die resolution.

## 15. Movement

Process movement step by step.

Conceptually:

```python
for step in range(movement):
    position = next_space(position)
    fire_pass_events()

    if forced_stop:
        break
```

Forced stop discards remaining movement.

Required because of:

- Rabbit Inn
- Rudder
- Anchor
- Cannon
- Small Shark Stand
- Rabbit Stand
- Pirate King Stand
- Big Bag Stand
- Start tile

## 16. Recursive activation

Prevent accidental infinite recursion.

For a single activation chain, track keys such as:

```python
ActivationKey(
    roll_id,
    source_instance_id,
    effect_id,
)
```

Do not globally suppress legitimate repeated activations.

Example: a wallet/well between two Halls of Wealth can be activated multiple times in one roll.

---

# 17. Prosperity buildings

## 17.1 Small Wallet — Green

Starting building.

```text
AFTER_ROLL:
Lv1 +1
Lv2 +2
Lv3 +3
Lv4 +4
```

## 17.2 Wishing Well — Blue

```text
AFTER_ROLL:
Lv1 +1
Lv2 +2
Lv3 +4
Lv4 +6

STAGE_CLEAR:
permanently increase this building's AFTER_ROLL coin amount by +1
```

## 17.3 Money Tree — Blue

```text
ON_STAY:
increase adjacent Prosperity buildings' dice coin gain permanently:
Lv1 +2
Lv2 +3
Lv3 +4
Lv4 +5

natural die == 3:
gain:
Lv1 2
Lv2 3
Lv3 6
Lv4 9
```

## 17.4 Lucky Color Gate — Purple, Prosperity + Luck

```text
die == 6:
    number_of_placed_LUCK * [2,4,6,8]

die == 1:
    number_of_placed_PROSPERITY * [2,4,6,8]
```

External dice-coin bonuses add to the resulting amount; they do not modify the per-building multiplier.

Forced dice-effect activation from Hall of Wealth or Rudder uses the Prosperity-count side.

## 17.5 Hall of Wealth — Purple

```text
natural die in {3,4}:
    activate DICE_EFFECT of adjacent Prosperity buildings

ON_STAY:
    permanently increase all Prosperity buildings' dice coin gain:
    Lv1 +2
    Lv2 +3
    Lv3 +4
    Lv4 +6
```

If both dice are 3/4, Hall of Wealth triggers once per roll.

## 17.6 Rabbit Inn — Gold

```text
ON_PASS:
    gain [6,12,18,24]
    choose random placed Prosperity building
    permanently increase its dice coin gain by [1,2,3,4]
```

Rabbit Inn does not choose itself for its own strengthening effect.

However, generic random Prosperity strengthening may still select Rabbit Inn, producing no useful dice-coin strengthening if it has no such effect.

---

# 18. Prosperity stands

## Mimi Stand

```text
AFTER_ROLL:
random placed Prosperity building:
    dice coin gain +1 permanently
```

## Rabbit Stand

```text
PASS_START:
random placed Prosperity building:
    dice coin gain +1 permanently
```

## Raccoon Stand

```text
when passing a Prosperity building:
    +1 coin
```

## Update Stand

```text
SHOP_REFRESH:
    charge += 1

if charge reaches 3:
    random placed Prosperity building dice coin gain +1
```

Opening the shop due to start forced stop counts as `SHOP_REFRESH`.

---

# 19. Promotion buildings

## 19.1 Piggy Bank — Green

Starting building.

```text
natural die == 1:
    +2 coin
    +2 XP

ON_SELL bonus:
Lv1 +1
Lv2 +8
Lv3 +25
Lv4 +45
```

## 19.2 Piglet Bank — Blue

```text
AFTER_ROLL:
    +1 XP

ON_SELL bonus:
Lv1 +3
Lv2 +15
Lv3 +35
Lv4 +65
```

## 19.3 Small Bookstore — Blue

Use current values, not February legacy values.

```text
ON_STAY:
    self and adjacent buildings gain XP:
    Lv1 +2
    Lv2 +4
    Lv3 +6
    Lv4 +8

ON_PASS:
    gain:
    Lv1 3
    Lv2 6
    Lv3 9
    Lv4 12
```

## 19.4 Beckoning Cat Vault — Purple

```text
AFTER_ROLL:
    every Piggy Bank and Piglet Bank gains XP:
    Lv1 +1
    Lv2 +1
    Lv3 +2
    Lv4 +2

ON_PASS:
    gain base [1,2,2,3] + accumulated_pass_bonus

when a Piggy Bank or Piglet Bank is sold:
    this vault.accumulated_pass_bonus += 1
```

Each placed vault observes the sale independently.

## 19.5 Fox Antique Shop — Gold

```text
natural die == 5:
```

Lv1:

```text
self +1 XP
random 1 building +1 XP
```

Lv2:

```text
self +1 XP
random 2 buildings +1 XP
```

Lv3:

```text
self +2 XP
random 2 buildings +2 XP
```

Lv4:

```text
self +2 XP
random 3 buildings +2 XP
```

On pass:

```text
generate one:
    Piggy Bank
    Piglet Bank
```

The exact probability of the two generated types is unresolved.

---

# 20. Promotion stands

Current Japanese data is incomplete.

Known names include:

```text
Pig Stand
Palunan Stand
```

Do not hard-code disputed current values.

See `RULE_STATUS.md`.

---

# 21. Luck buildings

## 21.1 Dice Sculpture — Green

Starting building.

```text
for each natural die == 6:
    gain:
    Lv1 6
    Lv2 12
    Lv3 18
    Lv4 24
```

## 21.2 Four-leaf Inn — Blue

```text
for each natural even die:
    gain [2,4,6,8]

for each natural die == 6:
    permanently increase own dice coin gain by +1
```

With two even dice, payout triggers twice.

Forced dice-effect activation:

```text
even payout: yes
natural-6 permanent growth: no
```

## 21.3 Lucky Star Coin Pond — Purple

```text
when rolling two dice:
    gain [6,12,18,24] once per roll

natural die == 1:
    next action uses two dice
```

Forced dice-effect activation may trigger the "next action uses two dice" effect.

## 21.4 Dice Tower — Purple

```text
natural die == 4:
    remove random placed Dice Sculpture
    inherit its XP
    permanently increase own dice coin gain by [6,8,10,12]

natural die == 6:
    gain [8,16,24,36] + accumulated dice bonus
```

Forced dice-effect activation uses the 4-side absorption effect.

If a two-die roll contains one 4 and one 6, both conditions may resolve.

## 21.5 Hologram Experience Hut — Gold

```text
ON_PASS:
    next action uses two dice

when rolling two dice:
    gain (sum of dice) * [1,2,3,4]
```

---

# 22. Luck stands

## Jasmine Stand

```text
WHEN_ROLLING:
    charge += 1

charge 4:
    next action rolls two dice
```

## Fried Shrimp Stand

```text
natural die == 1:
    next die forced to 6
```

## Three-leaf Stand

```text
for each natural die == 6:
    charge += 1

charge 6:
    gain random Luck building
```

---

# 23. Pirate buildings

## 23.1 Treasure — Green

```text
ON_STAY:
    current_amount =
        [12,18,24,30]
        + stay_coin_bonus
        - treasure_decay

    gain max(current_amount, configured_minimum)
    treasure_decay += 1
```

Triggered stay effects also consume one decay step.

Known trigger sources include:

- Rudder
- Cannon
- Captain Hat
- Great Shark Stand

Merging an old decayed Treasure into a fresh Treasure target can reset decay because target state is retained.

Do not transfer `treasure_decay` from merge material to target unless a later verified rule says otherwise.

## 23.2 Sail — Blue

```text
ON_PASS:
    [2,4,6,8]

ON_STAY:
    [4,8,12,16]

for each die == 4:
    [4,8,12,16]
```

## 23.3 Rudder — Blue, Luck + Pirate

```text
ON_PASS:
    random one placed Treasure:
        activate ON_STAY

ON_STAY:
    gain [6,12,18,24]

    random placed Luck building except Rudder:
        activate DICE_EFFECT
```

## 23.4 Anchor — Purple

```text
ON_PASS:
    immediately stop movement
    discard remaining movement
    gain [4,8,12,16]
    force next die to 4
```

## 23.5 Cannon — Purple

```text
for each die == 4:
    activate ON_STAY of adjacent Treasure and Sail

ON_PASS:
    gain one Treasure
    gain [4,8,12,16]
```

## 23.6 Captain Hat — Gold

```text
ON_STAY:
    for each placed Treasure:
        activate Treasure.ON_STAY

    N = number of affected Treasures

    remove all affected Treasures

    captain_pass_bonus += N * [12,16,20,24]

ON_PASS:
    gain [8,16,24,32] + captain_pass_bonus
```

Treasure effects must resolve before removal.

---

# 24. Pirate stands

## Pirate King Stand

```text
PASS_START:
    every Pirate building:
        pass_coin_bonus += 4
        stay_coin_bonus += 4
```

This strengthens pass/stay coin amounts, not arbitrary die-trigger payouts.

## Great Shark Stand

```text
for each die == 4:
    charge += 1

charge 4:
    activate ON_STAY of every Treasure and Sail
```

## Shovel Stand

```text
whenever Treasure.ON_STAY is activated:
    charge += 1

charge 8:
    gain 88
```

Triggered stay effects count.

## Small Shark Stand

```text
PASS_START:
    gain number_of_placed_PIRATE_buildings
```

---

# 25. Common stands

## Big Bag Stand

```text
PASS_START:
    gain a random copy of one currently placed building
```

## Roller Stand

```text
LAND_ON coin tile or card tile:
    corresponding building gains 5 XP
```

Exact mapping of "corresponding building" depends on verified board topology.

## Secret Book Stand

```text
TURN_START:
    random placed building gains 1 XP
```

Lv4 can be selected, potentially wasting the XP.

## Credit Card Stand

```text
TURN_START:
    gain floor(wallet / 50)
```

---

# 26. Forced DICE_EFFECT behavior

Do not simulate forced dice activation by inventing a die result.

Known behavior:

```text
Lucky Color Gate:
    forced effect uses Prosperity-count payout side

Dice Tower:
    forced effect uses 4-side absorption

Lucky Star Coin Pond:
    forced effect can enable next two-dice action

Four-leaf Inn:
    forced effect gives even payout
    does not perform natural-6 permanent growth

Dice Sculpture:
    forced effect gives its coin payout
```

Unknown forced behavior for any other building must remain unresolved rather than guessed.

---

# 27. Scoring

Current model:

```text
FinalScore =
    progress_score
    + star_coin_score
    + building_score
```

Progress score:

- difficulty-specific progression score

Star coin score:

- one half of final wallet
- current exact rounding remains unresolved; legacy evidence supports ceiling

Building score:

- current evidence says placed buildings are counted
- warehouse/inventory inclusion differs in legacy material and should not be assumed current

Palunan interaction with score remains unresolved.

## Known aggregate progress scores

```text
1-1 = 320
1-2 = 700
1-3 = 855
```

Current known stage counts:

```text
1-1: 5 stages
1-2: 6 stages
1-3: 6 stages
```

Known first-stage quota evidence:

```text
stage 1 = 15
```

Do not infer missing stage quotas from totals.

---

# 28. Shop

Legacy rarity distribution:

| Stage | Green | Blue | Purple | Gold |
|---|---:|---:|---:|---:|
| 1 | 70% | 28% | 2% | 0% |
| 2 | 60% | 34% | 5% | 1% |
| 3 | 50% | 40% | 8% | 2% |
| 4 | 34% | 48% | 15% | 3% |
| 5 | 31% | 45% | 20% | 4% |
| 6 | 30% | 42% | 23% | 5% |

Legacy behavior:

- refresh cost increases by 5
- capped at 50
- refresh count itself unlimited

These are not safe current defaults without explicit assumption mode.

Unknown current details include:

- rarity probabilities
- number of shop slots
- distribution inside a rarity
- purchase/refill behavior
- initial refresh cost

Represent shop distribution behind an interface.

Example:

```python
class BuildingDistribution(Protocol):
    def outcomes(self, state: GameState) -> list[WeightedOutcome]:
        ...
```

Do not reuse one distribution object for shop, card tile, and stand rewards unless verified.

---

# 29. Card tile

Current confirmed behavior:

```text
stopping on card tile -> gain one random building
```

Unknown distribution:

- uniform among all eligible buildings
- rarity first, then building
- same distribution as shop
- separate card distribution

Keep as configurable/unknown.

---

# 30. Stand offers

Legacy:

```text
after each stage:
    choose one from 3 random stands
```

Current pack selection restricts which stand pools may appear.

Offer count and exact distribution remain legacy/unknown unless explicitly configured.

---

# 31. Management actions

At minimum:

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

The solver should treat the pre-roll management period as a sequence of actions, not as one isolated action.

Use canonicalization to merge different action sequences reaching the same management state.

## Dominance

A state may dominate another only when all strategically relevant state is equivalent and the dominating state has no worse resources.

Do not compare only board layout and wallet.

Include at least:

- wallet
- stage progress
- building internal counters
- stand charges
- shop state
- forced die effects
- inventory
- permanent bonuses

---

# 32. Exact chance nodes

Random effects must enumerate weighted outcomes in exact mode.

Example:

```python
@dataclass(frozen=True)
class WeightedOutcome:
    probability: Fraction
    state: GameState
    events: tuple[EventLogEntry, ...]
```

Probability sum at each chance node must equal 1.

Use `fractions.Fraction` or another exact rational representation in exact solver paths where practical.

---

# 33. Search

Full-game exact DP is expected to be too large.

Use a hybrid.

## Near horizon

Use Expectimax for approximately 2–4 rolls.

Enumerate:

- dice outcomes
- known random-target outcomes
- known random rewards
- management decisions

## Long horizon

Use:

- MCTS
- Monte Carlo rollout
- beam search

or a suitable hybrid.

Expose user-configurable computation budgets.

Suggested presets:

```text
FAST
NORMAL
DEEP
VERY_DEEP
```

Also allow explicit iteration counts.

---

# 34. Transposition

Required.

Equivalent states should hash to the same canonical representation.

Do not let arbitrary instance ids prevent state merging.

For buildings, canonicalization should consider:

- type
- level
- XP
- location
- permanent bonuses
- internal counters

---

# 35. Chance-node compression

Two-die rolls start as 36 ordered outcomes.

Compress only when semantics are identical.

Examples that may prevent compression:

- per-die triggers
- one specifically forced die
- die-index-sensitive future rules

Correct probability weight must be retained.

---

# 36. GUI

Use PySide6.

Minimum screens/panels:

## Game State

Editable:

```text
Difficulty
Stage
Turns remaining
Wallet
Stage progress
Current position
Selected card packs
```

## Board

Show a 16-space ring.

For each building lot show/edit:

```text
type
level
XP
dice bonus
pass bonus
stay bonus
special counters
```

## Inventory

Edit owned unplaced buildings.

## Stands

Edit owned stands and charges.

## Shop

Edit current offers.

## Solver

Controls:

```text
Calculate
Stop
Objective mode
Clear threshold
Risk parameter
Compute budget
```

Results:

```text
#1 recommended management sequence
EV
P(clear)
confidence / exactness status

#2
...

#3
...
```

## Rule Status

Show:

```text
verified/current
legacy
inferred
unknown
```

and list unresolved rules that prevent exact results.

---

# 37. Strict exact mode

Provide a mode in which unresolved rules prevent an "exact" solution.

Do not simply crash.

Example GUI result:

```text
Exact calculation cannot proceed.

Required unresolved rules:
- card_tile_distribution
- current_shop_stage_4_distribution
```

Allow the user to enter assumptions in configuration and rerun.

---

# 38. Empirical calibration

Provide an optional mechanism for recording observations and estimating unknown probabilities.

Example shop observation record:

```text
stage
selected packs
slot_1
slot_2
...
```

For empirical estimates show:

- sample size
- estimated probability
- standard error
- 95% interval

Do not label empirical estimates as internal true game probabilities.

---

# 39. Simulation trace

Every simulation should optionally produce a detailed event trace.

Example:

```text
ROLL: [4, 6]

Cannon#2 natural die 4
  Treasure#5 triggered stay
    gain +11
    Treasure decay 3 -> 4
    Shovel charge 7 -> 8
    Shovel payout +88

DiceTower#1 natural die 4
  remove DiceSculpture#9
  absorb XP
  dice bonus +8

DiceTower#1 natural die 6
  gain +...
```

Trace should record:

- initial state
- management actions
- random outcomes
- event order
- wallet changes
- XP changes
- permanent bonus changes
- removals/additions
- forced die state
- seed where sampling is used

---

# 40. Implementation interface and explicit boundaries (2026-09-14)

This section documents the implementation; it does not add verified game rules.

- The core is a Python package under `src/astral_town`; the public integration facade is `rules.game.Game`.
- `GameState` is immutable. `stage_index` is zero-based and building `xp` is residual XP within the current level.
- Added lifecycle fields are `progress_score`, `status`, `phase`, `stand_offers`, `roll_id`, `last_roll`, `movement_remaining`, and `forced_stop`.
- A supplied `management` state is after that turn's `TURN_START` effects. `Game.start_turn` is available for explicit earlier inputs; later turns invoke it through the event queue.
- `EventEngine` uses weighted transitions and a work queue. `MOVE_STEP`, `ACTIVATE_BUILDING`, `ACTIVATE_STAND`, and `ADVANCE_STAGE` are implementation events in addition to the required events.
- Traces retain the complete immutable before/after states, source, activation cause, roll ID, die index, and activation chain.
- `RuleRegistry` resolves current/community values, rejects unresolved/inferred defaults, and records which explicit assumptions were used.
- Arbitrary board topology is supplied in a scenario. An inferred topology requires `accept_topology_assumption`; current 16-space size is checked independently.
- Generated-building distributions must supply complete instance templates. A type name alone does not invent initial level, XP, or counters.
- Inventory reward overflow remains unresolved, rather than discarding a reward or making the entire roll an illegal action.
- Supported explicit forced-effect assumptions map to named effects, never fabricated natural die outcomes. Unlisted values are rejected.

The JSON/YAML scenario format contains a typed `state`, typed `board`, optional complete `rules` registry,
explicit `assumptions`, and optional `allowed_actions`. `examples/` contains artificial fixtures, not current-game defaults.

## Search scope

Expectimax enumerates one/two-die and configured reward/target distributions using `Fraction`.
Management decisions can branch after stochastic actions; the separate bounded BFS helper only emits fixed deterministic plans.
Transposition keys preserve all strategic fields while ignoring arbitrary building/stand/offer identities.
Cached executable turn traces retain original identities and are not reused under renamed instances.

Expected score, clear probability, risk adjustment, and a clear-constrained score objective are available.
The constrained search retains attainable `(expected score, clear probability)` policy frontiers across chance branches;
its continuation is contingent and its output currently shows the first action.
This search does not optimize arbitrary externally randomized action mixtures.

An action-depth limit or explicitly restricted action set is reported as bounded search.
A nonterminal roll-horizon cutoff needs an explicit heuristic callable, and is reported as heuristic evaluation.
Node-budget exhaustion returns a diagnostic rather than a claimed optimum.

Long-horizon search currently uses seeded policy rollouts, not MCTS. The default continuation rolls immediately
and chooses the first offered stand; a custom policy can be supplied through the Python API.
Score intervals use a normal approximation and do not account for choosing the best among many sampled candidates.
Clear-probability intervals use Wilson intervals. Iteration budgets are deterministic; wall-clock budgets are not.

## GUI and calibration

The optional PySide6 GUI edits state/instances, renders the board, exposes search settings and cancellation,
and shows rule confidence and missing-rule diagnostics. Shop, topology, and rule/assumption editing use JSON panels.
All calculations run in a worker thread, with cancellation checked in both search and event processing.

Observation import/export supports CSV and JSON, grouped by rule ID and context.
Empirical distributions retain sample counts, intervals, and `inferred` confidence.
They can be applied only through explicit assumptions and matching stage/pack/difficulty context.
They never overwrite a verified-current rule, and unseen outcomes are not assigned invented probabilities.

Current-game global completion remains subject to the unresolved rules and verification criteria in
`RULE_STATUS.md`, `TARGETS.md`, and `docs/VALIDATION.md`.


## Explicit playable assumption mode (implementation amendment, 2026-09-14)

The current-game rules and confidence statements above are unchanged. Strict mode never fills an unknown distribution.
An explicitly selected `playable-defaults` profile may use the separate assumptions enumerated in RULE_STATUS.md / README.md:
uniform eligible target/type distributions, without-replacement multiple targets, fresh reward templates, uniform 3-subset stand
menus, independent uniform 3-slot shops, legacy purchase/refresh prices, no purchase refill, and Palunan total sale scope.
These are assumptions, not verification. Every result that references this profile must include `assumption-based` and the actually used assumptions.
Existing explicit and empirical distributions remain supported. Unspecified non-probability rules still require input.

`SELECT_STAND` does not consume the ordinary management-action depth, in either ordinary or clear-constrained search.
A rejected duplicate stand is an illegal action, not a solver crash. Palunan `base_only` versus `total` sale scope is configurable,
unknown, and independent from final-building-score interaction.
Search resource exhaustion is distinct from missing game rules; it must not put `search_node_budget` in missing rule IDs.
Rollout `max_rolls` is the maximum number of rolls for one complete trajectory, including a roll chosen as its first action.
