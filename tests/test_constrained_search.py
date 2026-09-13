from dataclasses import replace
from fractions import Fraction

from astral_town.model.outcomes import WeightedOutcome
from astral_town.model.enums import EventType as E
from astral_town.rules.registry import RuleRegistry
from astral_town.samples import model_sample
from astral_town.solver.expectimax import Expectimax
from test_game import game_fixture


def test_global_clear_constraint_preserves_tradeoff_policies():
    """A high-payoff failed branch can be balanced by a different clear branch."""
    real,_=game_fixture()
    class Engine:
        cancel=None
        def run(self,state,events):
            assert events[0].type==E.SELL_BUILDING
            score=200 if state.wallet in (10,100) else 20
            terminal=replace(state,wallet=score*2,status="failed",phase="terminal",buildings=(),inventory=())
            return (WeightedOutcome(Fraction(1),terminal),)
    class Game:
        registry=RuleRegistry.builtin({"score_wallet_rounding":"fraction"})
        board=real.board
        engine=Engine()
        exactness="assumption-based"
        def roll(self,state):
            if state.stage_index==0:
                return tuple(WeightedOutcome(Fraction(1,2),replace(state,stage_index=1,wallet=w)) for w in (10,20))
            score=100 if state.wallet==10 else 10
            terminal=replace(state,wallet=score*2,status="cleared",phase="terminal",buildings=(),inventory=())
            return (WeightedOutcome(Fraction(1),terminal),)
    state=replace(model_sample(),wallet=100,inventory=())
    result=Expectimax(Game(),horizon=2,management_depth=1,objective="EXPECTED_SCORE_WITH_CLEAR_CONSTRAINT",
                      clear_threshold=Fraction(1,2),allowed_actions={"END_MANAGEMENT_AND_ROLL","SELL"}).solve(state)
    best=result.recommendations[0]
    assert best.actions[0].kind=="END_MANAGEMENT_AND_ROLL"
    assert best.metrics.expected_score==105
    assert best.metrics.clear_probability==Fraction(1,2)
