"""Seeded policy rollouts; estimates compare explicit first actions, not a global optimum."""

from dataclasses import dataclass, replace
from fractions import Fraction
from math import sqrt
from random import Random
from statistics import mean, stdev
from time import monotonic

from astral_town.rules.errors import IllegalAction, CalculationCancelled
from astral_town.rules.registry import UnresolvedRule
from astral_town.rules.randomness import sample
from .evaluation import Metrics,terminal_metrics,utility
from .management_search import Action,actions,apply_action


PRESETS={"FAST":50,"NORMAL":200,"DEEP":1000,"VERY_DEEP":5000}


@dataclass(frozen=True)
class RolloutEstimate:
    action: Action
    metrics: Metrics
    samples: int
    score_interval_95: tuple[float,float] | None
    clear_interval_95: tuple[float,float]


@dataclass(frozen=True)
class RolloutResult:
    recommendations: tuple[RolloutEstimate,...]
    exactness: str
    seed: int
    cancelled: bool
    missing_rule_ids: tuple[str,...]
    limitations: tuple[str,...]
    assumptions_used: tuple[str,...] = ()
    empirical_rules_used: tuple[str,...] = ()


def wilson(successes,n):
    if n==0:return (0.0,1.0)
    p=successes/n
    z=1.959963984540054
    center=(p+z*z/(2*n))/(1+z*z/n)
    radius=z*sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return max(0,center-radius),min(1,center+radius)


def rollout(game,state,*,iterations=200,seed=0,max_rolls=100,time_budget=None,cancel=None,
            allowed_actions=None,policy=None,objective="EXPECTED_SCORE",risk_lambda=Fraction(1),clear_threshold=Fraction()):
    if iterations<1 or max_rolls<1:raise ValueError("Invalid rollout budget")
    rng=Random(seed)
    game.registry.used.clear();game.registry.missing.clear()
    deadline=monotonic()+time_budget if time_budget is not None else None
    options=tuple(a for a in actions(game,state) if allowed_actions is None or a.kind in allowed_actions)
    observations={a:[] for a in options}
    unavailable=set()
    missing=set()
    stopped=False
    def stop():return (cancel and cancel()) or (deadline is not None and monotonic()>=deadline)
    game.engine.cancel=stop
    def transition(current,action):
        return sample(game.roll(current) if action.kind=="END_MANAGEMENT_AND_ROLL" else apply_action(game,current,action),rng).state
    for _ in range(iterations):
        for first in options:
            if first in unavailable:continue
            if stop():stopped=True;break
            try:
                current=transition(state,first)
                for _step in range(max_rolls+1):
                    if stop():stopped=True;break
                    if current.status!="playing":break
                    if policy is not None:next_action=policy(game,current,rng)
                    elif current.phase=="stand_selection":next_action=Action("SELECT_STAND",target=0)
                    else:next_action=Action("END_MANAGEMENT_AND_ROLL")
                    current=transition(current,next_action)
                if stopped:break
                if current.status=="playing":raise UnresolvedRule("rollout_horizon_not_terminal")
                observations[first].append(terminal_metrics(game,current))
            except IllegalAction:
                unavailable.add(first)
            except UnresolvedRule as exc:missing.update(exc.rule_ids)
            except CalculationCancelled:stopped=True;break
        if stopped or missing:break
    result=[]
    for action,rows in observations.items():
        if not rows or action in unavailable:continue
        n=len(rows)
        metrics=sum(rows,Metrics())*Fraction(1,n)
        scores=[float(row.expected_score) for row in rows]
        interval=None
        if n>=2:
            radius=1.959963984540054*stdev(scores)/sqrt(n)
            interval=(mean(scores)-radius,mean(scores)+radius)
        result.append(RolloutEstimate(action,metrics,n,interval,wilson(sum(int(row.clear_probability) for row in rows),n)))
    scored=[(utility(r.metrics,objective,risk_lambda=risk_lambda,clear_threshold=clear_threshold),r) for r in result]
    scored=[(v,r) for v,r in scored if v is not None]
    scored.sort(key=lambda item:item[0],reverse=True)
    limitations=("fixed continuation policy (default: roll, select first stand)","approximate normal 95% score intervals; selection uncertainty not included")
    label="unresolved" if missing else "cancelled" if stopped and not scored else "simulation-estimated"
    return RolloutResult(tuple(r for _,r in scored[:3]) if not missing else (),label,seed,stopped,tuple(sorted(missing)),limitations,
                         tuple(sorted(game.registry.used & game.registry.assumptions.keys())),tuple(sorted(game.registry.used & game.registry.empirical.keys())))
