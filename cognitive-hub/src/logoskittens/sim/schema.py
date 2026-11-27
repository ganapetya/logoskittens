"""Judge verdicts for free speech, and the allowlist of the two English prompts."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

SCORES = (
    "subject_fidelity",
    "responsiveness",
    "initiative",
    "naturalness",
    "subject_card",
)
FAIL_FLAGS = ("corrected_human", "recited_human", "ended_conversation")
PROMPT_FILES = {
    "config/prompts/prompt-of-subject-creation_en.md",
    "config/prompts/ongoing_instruction_prompt_en.md",
}


class Scores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_fidelity: int = Field(ge=1, le=5)
    responsiveness: int = Field(ge=1, le=5)
    initiative: int = Field(ge=1, le=5)
    naturalness: int = Field(ge=1, le=5)
    subject_card: int = Field(ge=1, le=5)


class Flags(BaseModel):
    model_config = ConfigDict(extra="forbid")

    corrected_human: bool
    recited_human: bool
    ended_conversation: bool
    language_match: bool


class Critique(BaseModel):
    model_config = ConfigDict(extra="ignore")

    dimension: str = ""
    turn_index: int = Field(default=0, ge=0)
    text: str = Field(min_length=1)
    evidence: str = Field(min_length=1)


class JudgeVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=1)
    dialogue_id: str = Field(min_length=1)
    scores: Scores
    flags: Flags
    critiques: list[Critique]
    summary: str = Field(min_length=1)


class Mutation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    key: str = Field(min_length=1)
    value: str


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    kind: str
    mutations: list[Mutation] = Field(default_factory=list)
    needs_human: bool = False
    diff: str = ""


def parse_verdict(payload: dict) -> JudgeVerdict:
    try:
        return JudgeVerdict.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"judge JSON was invalid: {exc}") from exc


def blocked(verdict: JudgeVerdict) -> bool:
    flags = verdict.flags
    return (
        flags.corrected_human
        or flags.recited_human
        or flags.ended_conversation
        or not flags.language_match
    )


def mutation_allowed(path: str, key: str) -> bool:
    if path.startswith("/") or ".." in Path(path).parts:
        return False
    return path in PROMPT_FILES and key == "body"


def check_proposal(payload: dict) -> Proposal:
    proposal = Proposal.model_validate(payload)
    if proposal.kind != "config":
        raise ValueError("a code edit waits for a person")
    if len(proposal.mutations) != 1:
        raise ValueError("a proposal changes one prompt file")
    change = proposal.mutations[0]
    if not mutation_allowed(change.path, change.key):
        raise ValueError(f"not on the allowlist: {change.path} {change.key}")
    if not str(change.value).strip():
        raise ValueError("the prompt text is empty")
    return proposal


def apply_proposal(root: Path, payload: dict) -> list[str]:
    """Replace one allowlisted prompt file under ``root``."""
    proposal = check_proposal(payload)
    base = root.resolve()
    written: list[str] = []
    for change in proposal.mutations:
        path = (base / change.path).resolve()
        if not path.is_relative_to(base):
            raise ValueError(f"path escapes the root: {change.path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        text = change.value if change.value.endswith("\n") else change.value + "\n"
        path.write_text(text, encoding="utf-8")
        written.append(change.path)
    return written


def _verdicts(payload) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "verdicts" in payload:
        return list(payload["verdicts"])
    if isinstance(payload, dict) and "scores" in payload:
        return [payload]
    raise ValueError("expected a judge verdict or a list of them")


def compare_verdicts(before, after) -> dict:
    """Accept when a score rose, none fell, and no fail flag is set."""
    left = {item["scenario_id"]: parse_verdict(item) for item in _verdicts(before)}
    right = {item["scenario_id"]: parse_verdict(item) for item in _verdicts(after)}
    by_scenario: dict[str, dict] = {}
    improved: list[str] = []
    regressed: list[str] = []
    for scenario_id in sorted(set(left) | set(right)):
        if scenario_id not in left or scenario_id not in right:
            regressed.append(scenario_id)
            continue
        if blocked(right[scenario_id]):
            regressed.append(f"{scenario_id}.flags")
        row: dict[str, dict] = {}
        for name in SCORES:
            was = getattr(left[scenario_id].scores, name)
            now = getattr(right[scenario_id].scores, name)
            row[name] = {"before": was, "after": now}
            label = f"{scenario_id}.{name}"
            if now > was:
                improved.append(label)
            elif now < was:
                regressed.append(label)
        by_scenario[scenario_id] = row
    left_only = next(iter(left.values())) if len(left) == 1 else None
    right_only = next(iter(right.values())) if len(right) == 1 else None
    return {
        "baseline_run": left_only.dialogue_id if left_only else "",
        "candidate_run": right_only.dialogue_id if right_only else "",
        "by_scenario": by_scenario,
        "improved": improved,
        "regressed": regressed,
        "accept": bool(improved) and not regressed,
    }
