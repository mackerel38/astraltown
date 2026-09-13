# Implementation validation

Date: 2026-09-14. Environment: Python 3.14.7, pytest 9.1.1, PySide6 6.11.2.
This records software checks, not verification of the real game's rules.

Latest full run: **129 passed**, including the optional offscreen Qt subprocess check.
All three documented solver scenarios were rerun, and two separate NORMAL / 200-trial CLI runs
with seed 42 produced identical output with three recommendations.

## Phase checks

The implementation was exercised sequentially with pytest after each group:

| Coverage reached | Passing tests at that point |
|---|---:|
| Bootstrap | 5 |
| Model/registry | 14 |
| Deterministic engine | 31 |
| Dice/movement | 41 |
| Prosperity | 54 |
| Promotion | 67 |
| Luck | 76 |
| Pirate | 84 |
| Common stands/scoring | 95 |
| Full-turn integration/management | 103 |
| Expectimax | 109 |
| Rollout | 111 |
| Calibration | 114 |
| Cache and subsequent regressions | See current `pytest` output. |

The suite includes hand-computable one/two-roll expectations, global clear-constraint tradeoffs,
all mandatory interaction families, probability normalization, reward impossibility checks,
unknown-rule blockers, cache identity/provenance, reproducible sampling, and optional Qt subprocess tests.

```bash
source .venv/bin/activate
pytest
python -m compileall -q src
python -m astral_town trace
python examples/scripted_effects.py
python -m astral_town solve --scenario examples/artificial.json --horizon 1 --management-depth 1
python -m astral_town solve --scenario examples/populated_assumptions.json --horizon 2 --management-depth 0
python -m astral_town solve --scenario examples/populated_comparison.json --horizon 1 --management-depth 1
python -m astral_town rollout --scenario examples/populated_comparison.json --iterations 200 --seed 42
python -m astral_town simulate --scenario examples/populated_assumptions.json --seed 42
```

## Artificial scenario results

`artificial.json` compares placing a Small Wallet in either lot, selling it, and rolling.
At depth 1 / horizon 1, placement then roll scores 24 with clear probability 1;
selling then rolling scores 22. The two placements tie, so the next-best gap is 0.

`populated_assumptions.json` has 16 spaces, 12 lots, 8 placed buildings, 4 stands, and 2 remaining rolls.
Its explicit action set contains only rolling. Exact branch enumeration gives expected score `28733/36`,
expected wallet `1444/9`, and clear probability 1 under the stated assumptions.

`populated_comparison.json` uses the same scale with one remaining turn and compares placement, sale, and rolling.
The top results at management depth 1 / horizon 1 are:

| Plan | Expected final score | Clear probability |
|---|---:|---:|
| Sell Piggy Bank #2, then roll | `1573/2` | 1 |
| Sell Small Bookstore #7, then roll | `2336/3` | 1 |
| Sell Sail #3, then roll | `778` | 1 |

All are reported as bounded search / assumption-based. These are not recommendations for an observed current game.

## Profiling

Before optimizing, the populated two-roll scenario was profiled with `cProfile`.
A measured seeded 50-trial roll-only run took approximately 0.85 seconds without turn reuse.
After adding a 128-entry turn-outcome cache, the same run took approximately 0.05 seconds,
with the same expected sample score `19952/25` and 93 cache hits.
These are illustrative measurements on this environment, not time assertions in tests.

The cache keys retain original instance IDs for executable traces. Strategic transpositions use separate canonical keys.
Cache hits restore the rule dependency set, so an assumption-dependent result cannot become labeled exact after reuse.
Unknown/failed transitions are not cached. Cancellation is checked before returning a cached result.

## GUI and observations

The PySide6 GUI was launched using `QT_QPA_PLATFORM=offscreen`. Checks covered editing and serializing state,
rendering the board, computing the placement result, cancellation, and safe worker shutdown.
Screenshots were inspected for layout. No actual game window was inspected.

Observation round trips cover CSV and JSON. The calibration CLI and explicit estimate import were run against
`examples/observations.json`, which is artificial. Different-stage context is rejected and inferred confidence is retained.

## Remaining verification

The project-wide current-game completion criterion remains open: no actual current-version state with verified
topology, full quota/turn data, distribution data, score details, and unresolved effect ordering was available.
The engine intentionally blocks those dependencies without explicit assumptions.
Full unrestricted-game performance and a full contingent-policy-tree UI remain outside the demonstrated coverage.
