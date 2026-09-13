"""Observation statistics; empirical frequencies never become verified rules."""

import csv
import json
from collections import Counter
from fractions import Fraction
from math import sqrt
from pathlib import Path

from .rollout import wilson


def load_observations(path):
    path=Path(path)
    if path.suffix==".json":
        data=json.loads(path.read_text(encoding="utf-8"))
        rows=data["observations"]
    elif path.suffix==".csv":
        with path.open(encoding="utf-8",newline="") as stream:
            rows=[{"rule_id":row["rule_id"],"context":json.loads(row["context"]),"value":json.loads(row["value"])} for row in csv.DictReader(stream)]
    else:raise ValueError("Observations must be CSV or JSON")
    for row in rows:
        if not isinstance(row.get("rule_id"),str) or not isinstance(row.get("context"),dict) or "value" not in row:
            raise ValueError("Each observation needs rule_id, context object, and value")
    return rows


def export_observations(rows,path):
    path=Path(path)
    if path.suffix==".json":path.write_text(json.dumps({"observations":rows},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    elif path.suffix==".csv":
        with path.open("w",encoding="utf-8",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=["rule_id","context","value"]);writer.writeheader()
            for row in rows:writer.writerow({"rule_id":row["rule_id"],"context":json.dumps(row["context"],ensure_ascii=False),"value":json.dumps(row["value"],ensure_ascii=False)})
    else:raise ValueError("Observations must be CSV or JSON")


def calibrate(rows):
    groups={}
    for row in rows:
        key=(row["rule_id"],json.dumps(row["context"],sort_keys=True,ensure_ascii=False))
        groups.setdefault(key,Counter())[json.dumps(row["value"],sort_keys=True,ensure_ascii=False)]+=1
    reports=[]
    for (rule_id,context),counts in sorted(groups.items()):
        n=sum(counts.values())
        frequencies=[]
        distribution=[]
        for value,count in sorted(counts.items()):
            probability=Fraction(count,n)
            frequencies.append({"value":json.loads(value),"count":count,"frequency":str(probability),"standard_error":sqrt(float(probability*(1-probability))/n),"interval_95":wilson(count,n)})
            distribution.append({"probability":str(probability),"value":json.loads(value)})
        reports.append({"rule_id":rule_id,"context":json.loads(context),"sample_count":n,"method":"empirical",
                        "confidence":"inferred","unseen_outcomes_not_estimated":True,"frequencies":frequencies,"distribution":distribution})
    return reports


def apply_empirical_assumption(scenario,report):
    """Explicit caller action; retain report provenance in the exported scenario."""
    if report.get("method")!="empirical" or report.get("sample_count",0)<1:raise ValueError("Invalid empirical report")
    from astral_town.scenario import from_scenario
    from astral_town.rules.registry import freeze
    from astral_town.rules.randomness import configured_distribution
    from astral_town.model.enums import RuleConfidence
    game,state=from_scenario(scenario)
    rule=game.registry.values.get(report["rule_id"])
    if rule and rule.confidence==RuleConfidence.VERIFIED_CURRENT:
        raise ValueError("Empirical import cannot override a verified_current rule")
    # This estimate applies only to its stated context, not all future stages/packs.
    context=report["context"]
    if "stage_index" in context and context["stage_index"]!=state.stage_index:raise ValueError("Empirical stage context mismatch")
    if "selected_packs" in context and set(context["selected_packs"])!={p.value for p in state.selected_packs}:raise ValueError("Empirical pack context mismatch")
    result=dict(scenario)
    result["empirical_assumptions"]={**scenario.get("empirical_assumptions",{}),report["rule_id"]:report}
    return result
