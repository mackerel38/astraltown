# RULE_STATUS.md

# Rule Confidence Registry

This file separates current verified rules from community-current, legacy, inferred, and unknown rules.

Do not silently promote a lower-confidence rule to `verified_current`.

## Confidence levels

### `verified_current`

Current-version behavior directly confirmed by current documentation or reproducible current-game evidence.

### `community_current`

Current-version community verification that is strong enough to implement by default, but not treated as direct official/in-game certainty.

### `confirmed_legacy`

Confirmed for an older version, especially the pre-May-21-2026 Astral Town rules.

May be used only in explicit legacy/assumption mode until re-verified.

### `inferred`

Reasonable inference from current behavior, but not directly confirmed.

Results depending on this must be labeled assumption-based.

### `unknown`

Insufficient evidence.

Do not guess.

---

# 1. Current high-confidence rules

## Core

| Rule | Status |
|---|---|
| Board has 16 spaces | verified_current |
| Yellow coin tile gives 5 coins on stop | verified_current |
| Green card tile gives one random building on stop | verified_current |
| Passing start causes forced stop | verified_current |
| Shop opens after start forced stop | verified_current |
| Start-shop opening counts as shop refresh for Update Stand | verified_current |
| Wallet and stage progress are distinct concepts | verified_current |
| Initial owned buildings: Small Wallet, Piggy Bank, Dice Sculpture | verified_current |
| Pack categories: Prosperity, Promotion, Luck, Pirate | verified_current |
| Hybrid building requires all relevant packs selected | verified_current |
| Lucky Color Gate requires Prosperity + Luck | verified_current |
| Rudder requires Luck + Pirate | verified_current |

## Dice

| Rule | Status |
|---|---|
| Normal die is 1–6 | verified_current |
| Two-dice movement uses sum | verified_current |
| Per-die effects can trigger independently | verified_current |
| Four-leaf Inn can trigger twice on two even dice | verified_current |
| Hall of Wealth triggers only once per roll even if both dice are 3/4 | verified_current |
| Dice Tower can resolve both 4-side and 6-side effects in one two-die roll | verified_current |
| Anchor forced 4 has priority over Fried Shrimp forced 6 | verified_current |
| Anchor can coexist with two-dice behavior by fixing one die | community_current |

## XP / levels

| Rule | Value | Status |
|---|---:|---|
| Lv1 -> Lv2 XP | 5 | verified_current |
| Lv2 -> Lv3 XP | 10 | verified_current |
| Lv3 -> Lv4 XP | 15 | verified_current |
| Lv4 maximum | yes | verified_current |
| Lv4 cannot be merge material | yes | verified_current |
| Same-building merge base XP | 5 | community_current |

## Sell values

| Rarity | Lv1 | Lv2 | Lv3 | Lv4 | Status |
|---|---:|---:|---:|---:|---|
| Green | 4 | 8 | 12 | 16 | community_current |
| Blue | 8 | 16 | 24 | 32 | community_current |
| Purple | 15 | 30 | 45 | 60 | community_current |
| Gold | 25 | 50 | 75 | 100 | community_current |

---

# 2. Prosperity buildings

## Small Wallet

```text
AFTER_ROLL:
[1,2,3,4]
```

Status: `verified_current`

## Wishing Well

```text
AFTER_ROLL:
[1,2,4,6]

STAGE_CLEAR:
own payout +1 permanently
```

Status: `verified_current`

## Money Tree

```text
ON_STAY adjacent Prosperity dice bonus:
[2,3,4,5]

natural 3 payout:
[2,3,6,9]
```

Status: `verified_current`

## Lucky Color Gate

```text
6 -> placed Luck count * [2,4,6,8]
1 -> placed Prosperity count * [2,4,6,8]
```

Status: `verified_current`

Forced DICE_EFFECT uses Prosperity-count side.

Status: `verified_current`

## Hall of Wealth

```text
natural 3/4:
activate adjacent Prosperity DICE_EFFECT

ON_STAY:
all Prosperity dice bonus += [2,3,4,6]
```

Status: `verified_current`

Once-per-roll behavior with two triggering dice:

Status: `verified_current`

## Rabbit Inn

```text
ON_PASS payout:
[6,12,18,24]

random placed Prosperity dice bonus:
+[1,2,3,4]
```

Status: `verified_current`

Own strengthening does not target self:

Status: `verified_current`

Generic random Prosperity strengthening may select Rabbit Inn and waste dice strengthening:

Status: `community_current`

---

# 3. Prosperity stands

| Stand | Rule | Status |
|---|---|---|
| Mimi | after roll, random placed Prosperity dice bonus +1 | verified_current |
| Rabbit | pass start, random placed Prosperity dice bonus +1 | verified_current |
| Raccoon | passing Prosperity building gives +1 coin | verified_current |
| Update | shop refresh charge +1; at 3, random Prosperity dice bonus +1 | verified_current |

---

# 4. Promotion buildings

## Piggy Bank

```text
natural 1:
+2 coin
+2 XP

sell bonus:
[1,8,25,45]
```

Status: `verified_current`

## Piglet Bank

```text
AFTER_ROLL:
+1 XP

sell bonus:
[3,15,35,65]
```

Status: `verified_current`

## Small Bookstore

Current values:

```text
ON_STAY XP:
[2,4,6,8]

ON_PASS payout:
[3,6,9,12]
```

Status: `verified_current`

Important legacy conflict:

```text
older XP values [2,3,4,5]
older pass payout [2,4,6,8]
```

Status: `confirmed_legacy`

Do not use old values.

## Beckoning Cat Vault

```text
AFTER_ROLL Piggy/Piglet XP:
[1,1,2,2]

ON_PASS base:
[1,2,2,3]
+ accumulated bonus

Piggy/Piglet sale:
this vault accumulated pass bonus +1
```

Status: `verified_current`

## Fox Antique Shop

Natural 5:

```text
Lv1: self +1 XP, random 1 +1 XP
Lv2: self +1 XP, random 2 +1 XP
Lv3: self +2 XP, random 2 +2 XP
Lv4: self +2 XP, random 3 +2 XP
```

Status: `verified_current`

On pass generates Piggy Bank or Piglet Bank.

Status: `verified_current`

Generation probability:

Status: `unknown`

---

# 5. Promotion stands

## Pig Stand

Known older claims conflict:

```text
4 building sales -> Piglet Bank
5 building sales -> Piglet Bank
```

Current threshold:

Status: `unknown`

## Palunan Stand

Legacy effect:

```text
building purchase price -25%
building sale price +25%
```

Status: `confirmed_legacy`

Unknown:

- whether percentages are still current
- exact rounding
- whether altered sell value affects final building score

---

# 6. Luck buildings

## Dice Sculpture

```text
each natural 6:
[6,12,18,24]
```

Status: `verified_current`

## Four-leaf Inn

```text
each natural even die:
[2,4,6,8]

each natural 6:
own dice coin gain +1 permanently
```

Status: `verified_current`

Forced DICE_EFFECT:

```text
payout yes
natural-6 permanent growth no
```

Status: `verified_current`

## Lucky Star Coin Pond

```text
two-dice roll:
[6,12,18,24] once per roll

natural 1:
next action uses two dice
```

Status: `verified_current`

Forced DICE_EFFECT can enable two-dice next action:

Status: `verified_current`

## Dice Tower

```text
natural 4:
remove random placed Dice Sculpture
inherit XP
own dice bonus += [6,8,10,12]

natural 6:
gain [8,16,24,36] + dice bonus
```

Status: `verified_current`

Forced DICE_EFFECT uses 4-side absorption:

Status: `verified_current`

## Hologram Experience Hut

```text
ON_PASS:
next action uses two dice

two-dice roll:
gain sum(dice) * [1,2,3,4]
```

Status: `verified_current`

---

# 7. Luck stands

| Stand | Rule | Status |
|---|---|---|
| Jasmine | each roll charge +1; at 4, next action two dice | verified_current |
| Fried Shrimp | natural 1 -> next die forced 6 | verified_current |
| Three-leaf | each natural 6 charge +1; at 6 gain random Luck building | verified_current |

Random Luck building distribution:

Status: `unknown`

---

# 8. Pirate buildings

## Treasure

Base ON_STAY:

```text
[12,18,24,30]
```

Status: `verified_current`

Each stay activation decreases future payout by 1:

Status: `verified_current`

Triggered stays also count:

Status: `verified_current`

Merging decayed Treasure into a fresh target can reset decay:

Status: `verified_current`

Minimum payout:

```text
0
```

Status: `inferred`

## Sail

```text
ON_PASS:
[2,4,6,8]

ON_STAY:
[4,8,12,16]

each die 4:
[4,8,12,16]
```

Status: `verified_current`

## Rudder

```text
ON_PASS:
random placed Treasure -> trigger ON_STAY

ON_STAY:
gain [6,12,18,24]
random placed Luck except Rudder -> trigger DICE_EFFECT
```

Status: `verified_current`

## Anchor

```text
ON_PASS:
forced stop
discard remaining movement
gain [4,8,12,16]
next die forced 4
```

Status: `verified_current`

## Cannon

```text
each die 4:
trigger adjacent Treasure/Sail ON_STAY

ON_PASS:
gain one Treasure
gain [4,8,12,16]
```

Status: `verified_current`

Treasure reward distribution / exact generated state if any variation exists:

Status: `unknown`

## Captain Hat

```text
ON_STAY:
trigger every placed Treasure ON_STAY
remove those Treasures
captain_pass_bonus += count * [12,16,20,24]

ON_PASS:
[8,16,24,32] + captain_pass_bonus
```

Status: `verified_current`

Trigger-before-remove ordering:

Status: `verified_current`

---

# 9. Pirate stands

| Stand | Rule | Status |
|---|---|---|
| Pirate King | pass start: every Pirate pass/stay coin bonus +4 | verified_current |
| Great Shark | each 4 charges; at 4 trigger all Treasure/Sail ON_STAY | verified_current |
| Shovel | each Treasure ON_STAY activation charges; at 8 gain 88 | verified_current |
| Small Shark | pass start gain placed Pirate building count | verified_current |

---

# 10. Common stands

| Stand | Rule | Status |
|---|---|---|
| Big Bag | pass start -> random copy of placed building | verified_current |
| Roller | coin/card tile landing -> corresponding building +5 XP | verified_current |
| Secret Book | turn start -> random placed building +1 XP | verified_current |
| Credit Card | turn start -> floor(wallet / 50) | verified_current |

"Corresponding building" board mapping for Roller:

Status: `unknown` until board topology is verified.

---

# 11. Stage / difficulty data

Known stage counts:

| Difficulty | Stages | Status |
|---|---:|---|
| 1-1 | 5 | verified_current |
| 1-2 | 6 | verified_current |
| 1-3 | 6 | verified_current |

Known total progress scores:

| Difficulty | Total | Status |
|---|---:|---|
| 1-1 | 320 | verified_current |
| 1-2 | 700 | verified_current |
| 1-3 | 855 | verified_current |

Known first-stage quota:

```text
15
```

Status: `verified_current`

Per-stage quota sequences:

Status: `unknown`

Legacy quota sequence:

```text
[15,35,80,120,233,350]
```

Status: `confirmed_legacy`

Legacy rolls per stage:

```text
8
```

Status: `confirmed_legacy`

Current rolls per stage:

Status: `unknown`

---

# 12. Score

Current formula structure:

```text
FinalScore =
progress_score
+ star_coin_score
+ building_score
```

Status: `verified_current`

Star coin component = half of final wallet:

Status: `verified_current`

Rounding:

```text
ceil(wallet / 2)
```

Status: `confirmed_legacy`

Current rounding:

Status: `unknown`

Current building-score scope appears to use placed buildings:

Status: `community_current`

Legacy material may include warehouse/inventory:

Status: `confirmed_legacy`

Palunan interaction with score:

Status: `unknown`

---

# 13. Shop

Legacy purchase prices:

```text
Green 8
Blue 16
Purple 30
Gold 50
```

Status: `confirmed_legacy`

Green purchase price 8 has current supporting evidence.

Status: `community_current`

All other current purchase prices:

Status: `unknown`

Legacy rarity distribution:

| Stage | Green | Blue | Purple | Gold |
|---|---:|---:|---:|---:|
| 1 | 70% | 28% | 2% | 0% |
| 2 | 60% | 34% | 5% | 1% |
| 3 | 50% | 40% | 8% | 2% |
| 4 | 34% | 48% | 15% | 3% |
| 5 | 31% | 45% | 20% | 4% |
| 6 | 30% | 42% | 23% | 5% |

Status: `confirmed_legacy`

Legacy refresh:

```text
refresh cost +5 each time
cap 50
unlimited refresh count
```

Status: `confirmed_legacy`

Unknown current shop data:

- rarity probabilities
- slot count
- per-building weights
- post-purchase refill behavior
- initial refresh cost
- whether selected packs alter only eligibility or also weights

---

# 14. Card tile

Behavior:

```text
gain one random eligible building
```

Status: `verified_current`

Probability model:

Status: `unknown`

Possible models not to assume:

- uniform among eligible buildings
- rarity-first
- shop distribution
- card-specific distribution

---

# 15. Stand offers

Legacy:

```text
after each stage:
choose 1 from 3 random stands
```

Status: `confirmed_legacy`

Current pack-based pool restriction:

Status: `verified_current`

Current offer count:

Status: `unknown`

Current stand weights:

Status: `unknown`

---

# 16. Random target semantics

Text usually says "random".

Uniform among eligible targets:

Status: `inferred`

Multiple-target sampling with or without replacement:

Status: `unknown` unless explicitly verified for a specific effect.

Exact solver must keep the distribution configurable.

---

# 17. Initial economy / capacity

Legacy:

```text
initial unlocked lots = 6
maximum lots = 12
initial inventory capacity = 5
additional lot prices = [10,25,40,55,70,85]
```

Status: `confirmed_legacy`

Current:

- initial wallet
- unlocked lot count
- maximum lot count
- inventory capacity
- land prices

Status: `unknown`

---

# 18. Merge semantics

Base same-building merge XP 5:

Status: `community_current`

Whether source accumulated XP transfers:

Status: `unknown`

Whether arbitrary internal counters transfer:

Status: `unknown`

Known exception:

```text
Treasure decay does not need to transfer when a fresh Treasure is the target.
```

Status: `verified_current`

---

# 19. Forced die interactions

Known:

```text
Anchor forced 4 > Fried Shrimp forced 6
```

Status: `verified_current`

Unknown:

- whether lower-priority effect is consumed or retained
- exact ordering when several future-die modifiers coexist
- complete semantics with all two-dice sources

---

# 20. Outstanding unknowns required for exact global optimization

These should remain visible in the GUI / diagnostics until resolved:

```text
1-1 / 1-2 / 1-3 per-stage quotas
current rolls per stage
initial wallet
current inventory capacity
current unlocked/max land count
current land purchase prices
exact 16-space/lot topology
current shop rarity probabilities
shop per-building weights
shop slot count
shop refill behavior
current refresh pricing
card tile distribution
stand offer count
stand distribution
Pig Stand threshold
current Palunan percentages
Palunan rounding
Palunan interaction with final building score
Fox Antique Shop generation probability
Three-leaf reward distribution
Big Bag random-copy distribution if non-uniform
random-target uniformity
multi-target replacement semantics
Treasure minimum payout
source-XP merge transfer
current final-wallet half rounding
exact simultaneous-event priority in unresolved cases
forced-die modifier consumption rules
```

---

# 21. Implementation dependencies kept unresolved (2026-09-14)

No new in-game verification was performed during implementation. The confidence assignments above remain authoritative.
The following implementation dependencies are represented explicitly, rather than resolved by inference:

| Rule IDs / family | Reason / supported explicit assumptions |
|---|---|
| `gain_progress_sources` | Whether each source category (`building`, `stand`, `tile`, `sale`) counts toward the quota must be supplied; spending never reduces progress. |
| `xp_max_storage` | Storage of excess/residual XP at Lv4 is not stated; explicit `discard` / `retain`. |
| `simultaneous_event_order`, `roll_effect_order` | Supported assumed order is board then stands; die events vs per-roll conditions are separately configurable. |
| `four_leaf_growth_order` | Whether natural-6 growth precedes or follows that payout is not stated. |
| `<TYPE>.natural_cardinality`, `LUCKY_COLOR_GATE.different_face_branches` | Unstated duplicate-face or distinct-side two-die activation behavior is not promoted to per-die. Known per-die effects and Hall's once-per-roll behavior retain their documented status. |
| `stand_charge_consumption` | Reset vs threshold subtraction after activation is not stated. |
| `empty_random_target`, `insufficient_random_targets` | Behavior with no / too few eligible targets is not stated. |
| `forced_<BUILDING_TYPE>` | Forced behavior not listed in SPEC §26 is unresolved. In particular, Hall's neighboring Wallet/Well/Money Tree/Hall behavior is not inferred from their natural triggers. |
| `forced_die_index`, `forced_die_tie_order` | Which die is fixed and equal-priority modifier resolution are not fully specified. |
| `vault_xp_scope`, `fox_self_target`, `dice_tower_xp_transfer` | Owned vs placed XP targets, Fox self-eligibility, and residual vs cumulative absorbed XP require explicit input. |
| `big_bag_copy_state`, `big_bag_template` | A copied building's retained/reset instance fields are not stated. |
| `generated_building_state`, reward templates | New reward instance attributes are not silently set to fresh Lv1 defaults. |
| `inventory_reward_overflow` | A full inventory does not silently destroy rewards, reject a roll, or invent a replacement menu. |
| `refresh_prices`, `shop_refill_distribution`, `purchase_refill_counts_as_refresh` | Current refresh pricing and purchase-refill behavior are unresolved. |
| `stage_clear_timing`, `stage_progress_reset`, `stage_progress_scores` | Exact stage-check timing, next-stage progress carry/reset, and per-stage score allocation are not derived from aggregate totals. |
| `score_building_value` | The numeric building-score mapping is not inferred from sell values without an explicit assumption. |
| `stand_selection_duplicates` | Duplicate stand selection is not assigned a default behavior. |

Some IDs refer to alternative implementations of an unknown rule, not claims that the game uses one of those alternatives.
Unsupported configuration values are rejected. `treasure_minimum = 0` and uniform random targeting remain `inferred`
and are blocked unless explicitly supplied as assumptions.

The runtime registry is `src/astral_town/data/rules.json`. It includes a source and confidence for every stored rule value.
Missing dynamically named rules are also returned as unresolved IDs; they never receive a fallback.
The artificial examples opt into assumptions and are labeled accordingly.

## Empirical observations

Calibration output is labeled `method: empirical`, `confidence: inferred`, with sample count, frequency,
standard error, and Wilson 95% intervals. A larger sample never promotes a rule to `verified_current`.
Imported empirical assumptions remain separate from the registry and are checked against their context when used.

## Calculation diagnostics are not game rules

`cutoff_heuristic`, `search_node_budget`, `rollout_horizon_not_terminal`, and `stochastic_management_search`
describe implementation/search boundaries. They do not represent newly discovered in-game mechanics.
The last ID is specific to the fixed-plan BFS helper; Expectimax can evaluate stochastic management decisions directly.
