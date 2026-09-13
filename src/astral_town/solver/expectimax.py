"""Exact chance weighting in a bounded decision tree, with explicit diagnostics."""

from dataclasses import dataclass,replace
from fractions import Fraction

from astral_town.rules.registry import UnresolvedRule
from astral_town.rules.errors import IllegalAction, CalculationCancelled as Cancelled
from .evaluation import Metrics,terminal_metrics,utility
from .management_search import Action,actions,apply_action
from .transposition import TranspositionTable


@dataclass(frozen=True)
class Recommendation:
    actions: tuple[Action,...]
    metrics: Metrics
    value: Fraction


@dataclass(frozen=True)
class SearchResult:
    recommendations: tuple[Recommendation,...]
    exactness: str
    limitations: tuple[str,...]
    missing_rule_ids: tuple[str,...]
    transposition_hits: int
    nodes: int
    next_best_gap: Fraction | None
    cancelled: bool = False
    assumptions_used: tuple[str,...] = ()
    empirical_rules_used: tuple[str,...] = ()


class Expectimax:
    def __init__(self,game,*,horizon=2,management_depth=2,objective="EXPECTED_SCORE",risk_lambda=Fraction(1),
                 clear_threshold=Fraction(),allowed_actions=None,heuristic=None,cancel=None,node_budget=100000):
        if horizon<1 or management_depth<0 or node_budget<1:raise ValueError("Invalid search budget")
        if not 0<=clear_threshold<=1 or risk_lambda<0:raise ValueError("Invalid objective parameters")
        self.game=game
        self.horizon,self.management_depth=horizon,management_depth
        self.objective,self.risk_lambda,self.clear_threshold=objective,Fraction(risk_lambda),Fraction(clear_threshold)
        self.allowed_actions=frozenset(allowed_actions) if allowed_actions is not None else None
        self.heuristic,self.cancel,self.node_budget=heuristic,cancel,node_budget
        self.game.engine.cancel=cancel
        self.table=TranspositionTable()
        self.nodes=0
        self.limitations=set()
        self.missing=set()
        self.policy={}

    def _check(self):
        if self.cancel and self.cancel():raise Cancelled()
        self.nodes+=1
        if self.nodes>self.node_budget:raise UnresolvedRule("search_node_budget")

    def _value(self,metrics,*,root=False):
        return utility(metrics,self.objective,risk_lambda=self.risk_lambda,clear_threshold=self.clear_threshold)

    @staticmethod
    def _pareto(metrics):
        """Keep attainable policies trading expected score against clear probability."""
        frontier=[]
        for candidate in sorted(metrics,key=lambda m:(m.expected_score,m.clear_probability),reverse=True):
            if not any(old.expected_score>=candidate.expected_score and old.clear_probability>=candidate.clear_probability for old in frontier):
                frontier.append(candidate)
        return tuple(frontier)

    def _frontier_action(self,state,action,horizon,depth):
        rolled=action.kind=="END_MANAGEMENT_AND_ROLL"
        combined=(Metrics(),)
        for outcome in self._outcomes(state,action):
            choices=self._frontier_node(outcome.state,horizon-int(rolled),self.management_depth if rolled else max(0,depth-1))
            next_values=[]
            for prefix in combined:
                for choice in choices:
                    self._check()
                    next_values.append(prefix+choice*outcome.probability)
            combined=self._pareto(next_values)
        return combined

    def _frontier_node(self,state,horizon,depth):
        self._check()
        key=("frontier",state.canonical_key(),horizon,depth)
        cached=self.table.get(key)
        if cached is not None:return cached
        if state.status!="playing":result=(terminal_metrics(self.game,state),)
        elif horizon==0:
            if self.heuristic is None:raise UnresolvedRule("cutoff_heuristic")
            self.limitations.add("heuristic horizon cutoff")
            result=(self.heuristic(self.game,state),)
        else:
            candidates=[]
            for action in self._available(state,depth):
                try:candidates.extend(self._frontier_action(state,action,horizon,depth))
                except IllegalAction:continue
            if not candidates:raise UnresolvedRule("no_legal_management_continuation")
            result=self._pareto(candidates)
        self.table.put(key,result)
        return result

    def _available(self,state,depth):
        options=actions(self.game,state)
        if self.allowed_actions is not None:
            self.limitations.add("user-restricted management action set")
            options=tuple(a for a in options if a.kind in self.allowed_actions)
        if depth==0 and state.phase!="stand_selection":
            if any(a.kind!="END_MANAGEMENT_AND_ROLL" for a in options):self.limitations.add("management action-depth cutoff")
            options=tuple(a for a in options if a.kind=="END_MANAGEMENT_AND_ROLL")
        return options

    def _outcomes(self,state,action):
        return self.game.roll(state) if action.kind=="END_MANAGEMENT_AND_ROLL" else apply_action(self.game,state,action)

    def _action(self,state,action,horizon,depth):
        outcomes=self._outcomes(state,action)
        result=Metrics()
        rolled=action.kind=="END_MANAGEMENT_AND_ROLL"
        for outcome in outcomes:
            result=result+self._node(outcome.state,horizon-int(rolled),self.management_depth if rolled else max(0,depth-1))*outcome.probability
        return result

    def _node(self,state,horizon,depth):
        self._check()
        key=(state.canonical_key(),horizon,depth)
        cached=self.table.get(key)
        if cached is not None:return cached
        if state.status!="playing":result=terminal_metrics(self.game,state)
        elif horizon==0:
            if self.heuristic is None:raise UnresolvedRule("cutoff_heuristic")
            self.limitations.add("heuristic horizon cutoff")
            result=self.heuristic(self.game,state)
        else:
            candidates=[]
            for action in self._available(state,depth):
                try:metrics=self._action(state,action,horizon,depth)
                except IllegalAction:continue
                candidates.append((self._value(metrics),metrics,action))
            if not candidates:raise UnresolvedRule("no_legal_management_continuation")
            _,result,best_action=max(candidates,key=lambda item:item[0])
            self.policy[key]=(state,best_action)
        self.table.put(key,result)
        return result

    def _sequence(self,state,first):
        sequence=[first]
        action=first
        depth=self.management_depth
        while action.kind!="END_MANAGEMENT_AND_ROLL" and depth>0:
            outcomes=apply_action(self.game,state,action)
            if len(outcomes)!=1:
                self.limitations.add("management continuation branches on random outcome")
                break
            state=outcomes[0].state
            depth-=1
            record=self.policy.get((state.canonical_key(),self.horizon,depth))
            if record is None:break
            original,action=record
            def rebind(instance_id):
                if instance_id is None:return None
                template=replace(original.building(instance_id),instance_id=0)
                return next(b.instance_id for b in state.buildings+state.inventory if replace(b,instance_id=0)==template)
            source=rebind(action.source_id)
            target=rebind(action.target) if action.kind=="MERGE" else action.target
            if action.kind=="BUY":
                offer=next(o for o in original.shop_offers if o.offer_id==action.target)
                target=next(o.offer_id for o in state.shop_offers if o.price==offer.price and replace(o.building,instance_id=0)==replace(offer.building,instance_id=0))
            action=replace(action,source_id=source,target=target)
            sequence.append(action)
        return tuple(sequence)

    def solve(self,state):
        self.game.registry.used.clear()
        self.game.registry.missing.clear()
        self.table=TranspositionTable()
        self.nodes=0
        self.limitations.clear()
        self.missing.clear()
        self.policy.clear()
        recommendations=[]
        cancelled=False
        try:
            for action in self._available(state,self.management_depth):
                try:
                    if self.objective=="EXPECTED_SCORE_WITH_CLEAR_CONSTRAINT":
                        frontier=self._frontier_action(state,action,self.horizon,self.management_depth)
                        feasible=[m for m in frontier if m.clear_probability>=self.clear_threshold]
                        if not feasible:continue
                        metrics=max(feasible,key=lambda m:m.expected_score)
                        sequence=(action,)
                        self.limitations.add("clear-constrained continuation is contingent; first action displayed")
                    else:
                        metrics=self._action(state,action,self.horizon,self.management_depth)
                        sequence=self._sequence(state,action)
                except UnresolvedRule as exc:
                    self.missing.update(exc.rule_ids)
                    continue
                except IllegalAction:continue
                value=self._value(metrics,root=True)
                if value is not None:recommendations.append(Recommendation(sequence,metrics,value))
        except Cancelled:cancelled=True
        recommendations.sort(key=lambda r:(r.value,r.metrics.clear_probability),reverse=True)
        exactness=self.game.exactness
        if self.missing:exactness="unresolved"
        elif self.limitations:exactness="bounded-search" + (" / assumption-based" if exactness=="assumption-based" else "")
        if cancelled:exactness="cancelled"
        # Incomplete rule-dependent searches never offer provisional plans as optimal.
        if self.missing or cancelled:recommendations=[]
        top=tuple(recommendations[:3])
        gap=top[0].value-top[1].value if len(top)>1 else None
        return SearchResult(top,exactness,tuple(sorted(self.limitations)),tuple(sorted(self.missing)),self.table.hits,self.nodes,gap,cancelled,
                            tuple(sorted(self.game.registry.used & self.game.registry.assumptions.keys())),
                            tuple(sorted(self.game.registry.used & self.game.registry.empirical.keys())))
