"""Text-only free-speech simulation.

    python -m logoskittens.sim run --matrix config/sim/matrix.json --out data/sim-out
    python -m logoskittens.sim talk --persona "answers in one or two words" --turns 4
    python -m logoskittens.sim improve run
    python -m logoskittens.sim improve approve
    python -m logoskittens.sim improve reject
"""

import argparse
import json
import sys
from pathlib import Path

from logoskittens.sim.improve import (
    approve_pending,
    default_runner,
    find_repo,
    load_state,
    reject_pending,
    run_cycle,
    sim_root,
)
from logoskittens.sim.training_env import apply_sim_talk, complete_for, load_training
from logoskittens.sim.memory import LabMemory
from logoskittens.sim.runner import run_matrix, talk
from logoskittens.sim.schema import apply_proposal, compare_verdicts, parse_verdict


def _print(payload) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _cmd_run(args) -> None:
    apply_sim_talk(load_training(find_repo(args.matrix.resolve())).sim_talk)
    ids = run_matrix(args.matrix, args.out)
    for scenario_id in ids:
        print(scenario_id)


def _cmd_talk(args) -> None:
    apply_sim_talk(load_training(find_repo(Path.cwd())).sim_talk)
    trace = talk(
        language=args.language,
        material_id=args.material,
        persona=args.persona,
        turns=args.turns,
    )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _print(trace)


def _cmd_memory(args) -> None:
    lab = LabMemory(args.db)
    if args.memory_command == "query":
        _print(lab.query(persona=args.persona, cefr=args.cefr, limit=args.limit))
        return
    payload = _read(args.file)
    if args.kind == "critique" and isinstance(payload, dict) and "scores" in payload:
        print(lab.add_verdict(payload, persona=args.persona, cefr=args.cefr))
        return
    raise SystemExit("memory add needs a judge file with scores")


def _cmd_experiment(args) -> None:
    if args.experiment_command == "compare":
        _print(compare_verdicts(_read(args.before), _read(args.after)))
        return
    written = apply_proposal(args.root, _read(args.proposal))
    _print({"wrote": written})


def _cmd_judge(args) -> None:
    _print(parse_verdict(_read(args.file)).model_dump())


def _improve_paths(args) -> tuple[Path, Path]:
    repo = args.repo.resolve() if args.repo else find_repo(Path.cwd())
    work = args.work.resolve() if args.work else sim_root() / "improve"
    return repo, work


def _cmd_improve(args) -> None:
    repo, work = _improve_paths(args)
    if args.improve_command == "status":
        state = load_state(work)
        report = Path(state["report"]) if state.get("report") else None
        if report and report.is_file():
            sys.stdout.write(report.read_text(encoding="utf-8"))
        else:
            _print({"status": state.get("status", "idle")})
        return
    if args.improve_command in {"run", "approve"}:
        judge = complete_for(load_training(repo).judge)
    if args.improve_command == "run":
        state = run_cycle(repo, work, complete=judge, runner=default_runner, fresh=args.fresh)
    elif args.improve_command == "approve":
        approve_pending(repo, work, complete=judge, runner=default_runner)
        state = load_state(work)
    elif args.improve_command == "reject":
        state = reject_pending(repo, work)
    else:
        raise SystemExit(f"unknown improve command {args.improve_command}")
    report = Path(state["report"])
    sys.stdout.write(report.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Text-only LogosKittens free-speech simulation")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Replay the matrix through the free-speech graph")
    run.add_argument("--matrix", type=Path, required=True)
    run.add_argument("--out", type=Path, required=True)
    run.set_defaults(func=_cmd_run)

    spoken = sub.add_parser("talk", help="Run the pseudo-human against the buddy")
    spoken.add_argument("--language", default="en")
    spoken.add_argument("--material", default="norway_vacation_tunnels_fjords")
    spoken.add_argument("--persona", default="answers in one or two words")
    spoken.add_argument("--turns", type=int, default=4)
    spoken.add_argument("--out", type=Path)
    spoken.set_defaults(func=_cmd_talk)

    memory = sub.add_parser("memory", help="Read or append lab notes")
    memory.add_argument("--db", type=Path, default=sim_root() / "memory.db")
    memory_sub = memory.add_subparsers(dest="memory_command", required=True)
    query = memory_sub.add_parser("query")
    query.add_argument("--persona", default="")
    query.add_argument("--cefr", default="")
    query.add_argument("--limit", type=int, default=8)
    query.set_defaults(func=_cmd_memory)
    add = memory_sub.add_parser("add")
    add.add_argument("--kind", required=True)
    add.add_argument("--file", type=Path, required=True)
    add.add_argument("--persona", default="")
    add.add_argument("--cefr", default="")
    add.set_defaults(func=_cmd_memory)

    experiment = sub.add_parser("experiment", help="Compare scores or apply one prompt")
    experiment_sub = experiment.add_subparsers(dest="experiment_command", required=True)
    compare = experiment_sub.add_parser("compare")
    compare.add_argument("before", type=Path)
    compare.add_argument("after", type=Path)
    compare.set_defaults(func=_cmd_experiment)
    apply = experiment_sub.add_parser("apply")
    apply.add_argument("--proposal", type=Path, required=True)
    apply.add_argument("--root", type=Path, required=True)
    apply.set_defaults(func=_cmd_experiment)

    judge = sub.add_parser("judge", help="Check that a verdict file has the right keys")
    judge.add_argument("file", type=Path)
    judge.set_defaults(func=_cmd_judge)

    improve = sub.add_parser("improve", help="Score dialogues and propose one prompt change")
    improve.add_argument("--repo", type=Path)
    improve.add_argument("--work", type=Path)
    improve_sub = improve.add_subparsers(dest="improve_command", required=True)
    improve_run = improve_sub.add_parser("run")
    improve_run.add_argument("--fresh", action="store_true")
    improve_run.set_defaults(func=_cmd_improve)
    for name in ("approve", "reject", "status"):
        item = improve_sub.add_parser(name)
        item.set_defaults(func=_cmd_improve)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
