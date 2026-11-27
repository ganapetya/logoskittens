"""Replay frozen human lines through the free-speech graphs. No audio."""

import json
from pathlib import Path

from logoskittens.actors import load_actors
from logoskittens.graph import run_buddy_turn, run_prepare
from logoskittens.llm import complete
from logoskittens.materials import FileRawMaterialSource
from logoskittens.talk import SpokenSentence, ongoing_for, split_sentences


def load_matrix(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("matrix must be a list")
    return payload


def load_script(path: Path) -> list[str]:
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        text = raw.strip()
        if not text:
            continue
        if text.startswith("{"):
            item = json.loads(text)
            text = str(item.get("text") or item.get("line") or "").strip()
        if text:
            lines.append(text)
    return lines


def run_dialogue(
    *,
    scenario_id: str,
    language: str,
    material_id: str,
    lines: list[str],
    complete=complete,
    actors=None,
) -> dict:
    """Summarize once, then one buddy reply per frozen human line."""
    material = FileRawMaterialSource().load(language, material_id)
    subject = run_prepare(material.text, language, complete)
    roster = actors or load_actors()
    sentences: list[SpokenSentence] = []
    turns = []
    for human in lines:
        for piece in split_sentences(human):
            sentences.append(SpokenSentence(speaker="human", text=piece))
        ongoing = ongoing_for(subject, sentences, language, latest_human=human)
        solution = run_buddy_turn(ongoing, human, complete=complete, actors=roster)
        for piece in split_sentences(solution.speech.text):
            sentences.append(SpokenSentence(speaker="buddy", text=piece))
        turns.append(
            {
                "human": human,
                "buddy": solution.speech.text,
                "emotion": solution.emotion,
                "actor_id": solution.actor_id,
            }
        )
    return {
        "id": scenario_id,
        "language": language,
        "material_id": material_id,
        "subject": subject.model_dump(),
        "turns": turns,
        "transcript": [f"{item.speaker}: {item.text}" for item in sentences],
    }


def run_matrix(path: Path, out: Path, *, complete=complete) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    written = []
    root = path.parent
    for item in load_matrix(path):
        script = Path(item["script"])
        if not script.is_absolute():
            script = _find_script(script, root)
        trace = run_dialogue(
            scenario_id=item["id"],
            language=item["language"],
            material_id=item["material_id"],
            lines=load_script(script),
            complete=complete,
        )
        target = out / f"{item['id']}.json"
        target.write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(item["id"])
    return written


def talk(
    *,
    language: str,
    material_id: str,
    persona: str,
    turns: int,
    complete=complete,
) -> dict:
    """Live pseudo-human against the buddy. Not the accept gate."""
    from logoskittens.content import prompt_text

    material = FileRawMaterialSource().load(language, material_id)
    subject = run_prepare(material.text, language, complete)
    system = prompt_text("pseudo_human", language)
    actors = load_actors()
    sentences: list[SpokenSentence] = []
    dialogue = []
    for _index in range(turns):
        recent = "\n".join(f"- {item.speaker}: {item.text}" for item in sentences[-8:]) or "- (none yet)"
        user = (
            f"persona: {persona}\n"
            f"theme: {subject.theme}\n"
            f"recent:\n{recent}\n"
        )
        raw, _record = complete(user, system=system)
        payload = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
        human = str(payload["line"]).strip()
        for piece in split_sentences(human):
            sentences.append(SpokenSentence(speaker="human", text=piece))
        ongoing = ongoing_for(subject, sentences, language, latest_human=human)
        solution = run_buddy_turn(ongoing, human, complete=complete, actors=actors)
        for piece in split_sentences(solution.speech.text):
            sentences.append(SpokenSentence(speaker="buddy", text=piece))
        dialogue.append({"human": human, "buddy": solution.speech.text})
    return {
        "language": language,
        "material_id": material_id,
        "persona": persona,
        "subject": subject.model_dump(),
        "turns": dialogue,
    }


def _find_script(script: Path, matrix_dir: Path) -> Path:
    if script.is_file():
        return script
    for parent in [matrix_dir, *matrix_dir.parents]:
        candidate = parent / script
        if candidate.is_file():
            return candidate
        if (parent / "config").is_dir() and (parent / script).is_file():
            return parent / script
    return script
