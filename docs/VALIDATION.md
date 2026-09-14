# Implementation validation

Date: 2026-09-14. Local environment: Python 3.14.7, pytest 9.1.1, PySide6 6.11.2.
These are software checks, not verification of current-game rules or probabilities.

## Latest full verification

**181 passed**, including two optional offscreen Qt subprocess smoke tests.
`python -m compileall -q src` and `git diff --check` completed successfully.
All pre-existing entries in `rules.json` were compared with the previous commit: values, sources,
and confidence assignments are unchanged. New `palunan_sale_scope` and `purchase_prices` dependencies are unknown.

Executed locally using `.venv/bin/python` / `.venv/bin/pytest`:

```bash
pytest
python -m compileall -q src
python -m astral_town trace
python -m astral_town simulate --scenario examples/playable_defaults.json --profile playable-defaults --seed 42
python -m astral_town solve --scenario examples/artificial.json --horizon 1 --management-depth 1
python -m astral_town solve --scenario examples/populated_assumptions.json --horizon 2 --management-depth 0
python -m astral_town solve --scenario examples/populated_comparison.json --horizon 1 --management-depth 1
python -m astral_town solve --scenario examples/playable_defaults.json --mode strict --horizon 1 --management-depth 0
python -m astral_town solve --scenario examples/playable_defaults.json --profile playable-defaults --horizon 1 --management-depth 0
python -m astral_town solve --scenario examples/playable_defaults.json --profile playable-defaults --horizon 1 --node-budget 1
python -m astral_town rollout --scenario examples/playable_defaults.json --profile playable-defaults --iterations 1000 --seed 42 --max-rolls 1
```

The last command was run twice as separate CLI processes. Complete JSON outputs matched, including metrics,
intervals, used assumptions, labels and sample counts. The sampled event trace ran successfully (223 output lines).

## Review regressions exercised

- Ordinary Expectimax and clear-constrained frontier: depth 1 permits SELECT_STAND → PLACE → ROLL,
  giving score 24 and clear probability 1 in a hand-computable state. Fixed-plan BFS also permits this sequence.
- Duplicate prohibited stand candidate raises IllegalAction; both solver objectives evaluate the other legal candidate successfully.
- A search node budget of 1 returns budget-exhausted, without missing rule IDs. A completed root candidate can survive
  a later budget hit as bounded-search; unfinished candidates are discarded.
- Piggy and Piglet sale bonuses were tested with both Palunan scopes and an independent final-score setting.
  Omitting sale scope still raises the corresponding unknown rule.
- Counted game.roll calls confirm limits 0, 1, 2 and 3, for both a management first action and a roll first action.
  A terminal state reached on the last permitted roll is scored; nonterminal trajectories are not.

## Distribution and mode checks

Tests use Fraction probabilities without floating-point normalization. Coverage includes:

- Uniform random targets for N = 2, 3 and 4; Rabbit self-exclusion, placed-only eligibility and separate empty-target policy.
- Dynamic card pools under changed selected packs; hybrid pack requirements; fresh Lv1/XP0/bonus0/counter0 unplaced instances.
- Three-leaf eligible Luck-only pools; Fox Piggy/Piglet 1/2 each; deterministic fresh Cannon Treasure.
- Fox without-replacement target subsets and Big Bag uniform placed-instance selection with fresh template copies.
- Uniform stand 3-subsets with exact total probability 1, no permutations; small configured pools offer all types.
- Independent shop slot marginals and joint mass for Luck-only and all-pack pools; prices, repeated types,
  generated templates, real refresh/purchase events and no purchase refill.
- Refresh counts 0, 1, 8, 9 and 1000, including the permanent price cap.
- Explicit, empirical and synthetic verified distribution precedence over profile defaults without confidence promotion.
- Strict blocks the same card probability that playable mode resolves; cache reuse preserves used profile assumptions, including a profile → empirical → profile round trip.
- Budget-exhausted results retain the assumption-based label when a profile dependency was referenced.
- GUI mode switching, warning visibility, unchanged Rule Status confidence, result values, editor serialization and cancellation.

## Artificial scenario results

The three existing examples preserve their previous results:

| Scenario / best plan | Expected score | Clear probability |
|---|---:|---:|
| artificial: place Small Wallet, roll | 24 | 1 |
| artificial: sell Small Wallet, roll | 22 | 1 |
| populated_assumptions: roll-only, horizon 2 | 28733/36 | 1 |
| populated_comparison: sell Piggy #2, roll | 1573/2 | 1 |
| populated_comparison: sell Bookstore #7, roll | 2336/3 | 1 |
| populated_comparison: sell Sail #3, roll | 778 | 1 |

The new `playable_defaults.json` has 16 spaces, 12 lots, 8 placed buildings, 4 stands and one remaining roll.
It supplies artificial non-probability assumptions and leaves the card distribution unspecified.

| Mode | Actual result |
|---|---|
| Strict | unresolved; missing_rule_ids = [card_distribution]; no recommendation |
| playable-defaults, horizon 1 | bounded-search / assumption-based; EV = 2111/3; P(clear) = 1/3; expected wallet = 398/3 |
| playable-defaults, node budget 1 | budget-exhausted / assumption-based; missing_rule_ids empty |
| playable-defaults, seed 42, 1000 rollout trials | simulation-estimated / assumption-based; sample EV = 704641/1000; sample P(clear) = 343/1000 |

Only `card_distribution` and `generated_building_state` appear in `profile_assumptions_used` for this sample.
`assumptions_used` additionally lists the individual non-probability assumptions actually read. Unused shop defaults are absent.

## CI configuration

`.github/workflows/test.yml` defines Python 3.12 and 3.13 core jobs installing `.[test]`, running pytest and compileall.
A separate Python 3.12 job installs `.[gui,test]` and runs `QT_QPA_PLATFORM=offscreen pytest tests/test_ui.py`.
The local results above use Python 3.14.7; execution of the other versions is reported by
[the repository Actions runs](https://github.com/mackerel38/astraltown/actions/workflows/test.yml).

## Remaining limitations

No actual current-version topology, complete quota/turn data, or new in-game probability evidence was collected.
Unspecified non-probability rules (including inventory overflow, empty targets, duplicate stand legality,
Palunan percentages/rounding, and effect ordering) still need explicit input when reached.
Playable defaults are assumptions only; their successful tests do not verify them as current-game truth.

Exact shops enumerate N^3 outcomes, and rollouts currently enumerate the full transition before sampling it.
The search node budget does not bound event-expansion memory. Unrestricted full-game performance is not demonstrated.
Default rollout continuation remains roll / first stand; greedy stand evaluation is deferred and this is not MCTS.
The clear-constrained solver displays the first action, not the complete contingent policy tree.
