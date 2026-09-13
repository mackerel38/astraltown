from dataclasses import dataclass
from fractions import Fraction

from astral_town.rules.scoring import final_score


@dataclass(frozen=True)
class Metrics:
    expected_score: Fraction = Fraction()
    clear_probability: Fraction = Fraction()
    expected_wallet: Fraction = Fraction()
    expected_building_score: Fraction = Fraction()
    expected_progress_score: Fraction = Fraction()

    def __add__(self,other):return Metrics(*(a+b for a,b in zip(self.values(),other.values())))
    def __mul__(self,weight):return Metrics(*(a*weight for a in self.values()))
    def values(self):return (self.expected_score,self.clear_probability,self.expected_wallet,self.expected_building_score,self.expected_progress_score)


def terminal_metrics(game,state):
    score=final_score(state,game.registry)
    return Metrics(score.total,Fraction(state.status=="cleared"),Fraction(state.wallet),score.building,score.progress)


def utility(metrics,objective="EXPECTED_SCORE",*,risk_lambda=Fraction(1),clear_threshold=Fraction()):
    if objective=="EXPECTED_SCORE":return metrics.expected_score
    if objective=="CLEAR_PROBABILITY":return metrics.clear_probability
    if objective=="RISK_ADJUSTED_SCORE":return metrics.expected_score-risk_lambda*(1-metrics.clear_probability)
    if objective=="EXPECTED_SCORE_WITH_CLEAR_CONSTRAINT":
        return metrics.expected_score if metrics.clear_probability>=clear_threshold else None
    raise ValueError("Unknown objective")
