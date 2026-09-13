"""Command-line entry point."""

import json
import argparse

from astral_town.data.loader import load_builtin


def main() -> None:
    parser = argparse.ArgumentParser(description="Astral Town (implementation in progress)")
    parser.add_argument("command", choices=["config", "model", "trace", "simulate", "solve", "rollout", "gui", "calibrate", "import-estimate"], nargs="?", default="config")
    parser.add_argument("--observations")
    parser.add_argument("--output")
    parser.add_argument("--estimate")
    parser.add_argument("--report-index",type=int,default=0)
    parser.add_argument("--trace-output")
    parser.add_argument("--scenario", default="examples/artificial.json")
    parser.add_argument("--horizon", type=int, default=2)
    parser.add_argument("--management-depth", type=int, default=1)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--objective", default="EXPECTED_SCORE",choices=["EXPECTED_SCORE","CLEAR_PROBABILITY","EXPECTED_SCORE_WITH_CLEAR_CONSTRAINT","RISK_ADJUSTED_SCORE"])
    parser.add_argument("--clear-threshold",default="0")
    parser.add_argument("--risk-lambda",default="1")
    args = parser.parse_args()
    if args.command=="import-estimate":
        from pathlib import Path
        from astral_town.data.loader import load_file
        from astral_town.solver.calibration import apply_empirical_assumption
        if not args.estimate or not args.output:parser.error("--estimate and --output are required")
        report=json.loads(Path(args.estimate).read_text(encoding="utf-8"))[args.report_index]
        data=apply_empirical_assumption(load_file(args.scenario),report)
        Path(args.output).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("Empirical assumption imported; confidence remains inferred.")
    elif args.command == "calibrate":
        from astral_town.solver.calibration import load_observations,calibrate
        from pathlib import Path
        if not args.observations:parser.error("--observations is required")
        report=json.dumps(calibrate(load_observations(args.observations)),ensure_ascii=False,indent=2)
        if args.output:Path(args.output).write_text(report+"\n",encoding="utf-8")
        else:print(report)
    elif args.command == "gui":
        from astral_town.ui.app import run
        run(args.scenario)
    elif args.command in {"simulate", "solve", "rollout"}:
        from fractions import Fraction
        from random import Random
        from astral_town.data.loader import load_file
        from astral_town.scenario import from_scenario,to_plain
        from astral_town.rules.registry import UnresolvedRule
        from astral_town.rules.randomness import sample
        from astral_town.solver.expectimax import Expectimax
        from astral_town.solver.rollout import rollout
        try:
            data=load_file(args.scenario)
            game,state=from_scenario(data)
            if args.command=="simulate":
                result=sample(game.roll(state),Random(args.seed))
                if args.trace_output:
                    from pathlib import Path
                    from astral_town.model.serialization import encode
                    Path(args.trace_output).write_text(json.dumps({"seed":args.seed,"initial_state":encode(state),"events":encode(result.events)},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
                print(f"seed={args.seed}; exactness={game.exactness}; {data.get('description','')}")
                for entry in result.events:print(entry.describe())
                print(json.dumps({"state":to_plain(result.state)},ensure_ascii=False,indent=2))
            else:
                options=dict(objective=args.objective,clear_threshold=Fraction(args.clear_threshold),risk_lambda=Fraction(args.risk_lambda),allowed_actions=data.get("allowed_actions"))
                if args.command=="solve":
                    result=Expectimax(game,horizon=args.horizon,management_depth=args.management_depth,**options).solve(state)
                else:result=rollout(game,state,iterations=args.iterations,seed=args.seed,**options)
                print(json.dumps(to_plain(result),ensure_ascii=False,indent=2))
        except UnresolvedRule as exc:
            print(json.dumps({"exactness":"unresolved","missing_rule_ids":exc.rule_ids},ensure_ascii=False,indent=2))
        except ValueError as exc:
            parser.error(str(exc))
    elif args.command == "trace":
        from astral_town.samples import model_sample
        from astral_town.model.enums import EventType as E
        from astral_town.model.events import Event
        from astral_town.rules.engine import EventEngine
        from astral_town.rules.registry import RuleRegistry
        engine = EventEngine(RuleRegistry.builtin())
        result, = engine.run(model_sample(), (
            Event(E.MANAGEMENT_START),
            Event(E.GAIN_COIN, payload=(("amount", 10), ("progress", True))),
            Event(E.SPEND_COIN, payload=(("amount", 8),)),
            Event(E.GAIN_XP, source_id=1, payload=(("amount", 5),)),
            Event(E.MANAGEMENT_END),
        ))
        print("Artificial scripted sample; not current starting defaults")
        for entry in result.events:
            print(entry.describe())
        print(f"wallet={result.state.wallet}, progress={result.state.stage_progress}, wallet building level={result.state.building(1).level}")
    elif args.command == "model":
        from astral_town.samples import model_sample
        from astral_town.model.serialization import encode
        print(json.dumps(encode(model_sample()), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(load_builtin(), ensure_ascii=False, indent=2))
