"""LangGraph for free speech.

The prepare graph summarizes raw material once. Each human turn runs the buddy
graph: speak, then compile one ElementSolution. There is no end node and no
second speaker. buddy-two stays out of both graphs.
"""

from typing import Callable, TypedDict

from langgraph.graph import END, StateGraph

from logoskittens.llm import ComparisonRecord
from logoskittens.primitives import Actor, ElementSolutionModel, GroupSolution, TurnSlot
from logoskittens.talk import (
    BUDDY_ID,
    BuddyReply,
    LessonSubjectInput,
    OngoingConversation,
    active_buddy,
    buddy_reply,
    create_subject,
    solution_for,
)

CompleteFn = Callable[..., tuple[str, ComparisonRecord]]


class PrepareState(TypedDict, total=False):
    language_id: str
    raw_text: str
    subject: dict


class TurnState(TypedDict, total=False):
    language_id: str
    ongoing: dict
    latest_human: str
    line: str
    emotion: str
    solution: dict


def free_speech_group(task_id: str) -> GroupSolution:
    return GroupSolution(
        solution_id="group-free-speech",
        task_id=task_id,
        protocol="free_speech",
        turn_order=[TurnSlot(actor_id=BUDDY_ID, purpose="talk")],
    )


def build_prepare_graph(complete: CompleteFn):
    def summarize(state: PrepareState) -> dict:
        card = create_subject(state["raw_text"], state["language_id"], complete)
        return {"subject": card.model_dump()}

    graph = StateGraph(PrepareState)
    graph.add_node("summarize", summarize)
    graph.set_entry_point("summarize")
    graph.add_edge("summarize", END)
    return graph.compile()


def build_turn_graph(complete: CompleteFn, actors: dict[str, Actor]):
    def speak(state: TurnState) -> dict:
        ongoing = OngoingConversation.model_validate(state["ongoing"])
        reply = buddy_reply(ongoing, state.get("latest_human", ""), complete)
        return {"line": reply.line, "emotion": reply.emotion}

    def compile_line(state: TurnState) -> dict:
        reply = BuddyReply(line=state["line"], emotion=state["emotion"])
        ongoing = OngoingConversation.model_validate(state["ongoing"])
        voice = ongoing.personality.voice_id if ongoing.personality else ""
        solution = solution_for(reply, active_buddy(actors), state["language_id"], voice)
        return {"solution": solution.model_dump()}

    graph = StateGraph(TurnState)
    graph.add_node("speak", speak)
    graph.add_node("compile", compile_line)
    graph.set_entry_point("speak")
    graph.add_edge("speak", "compile")
    graph.add_edge("compile", END)
    return graph.compile()


def run_prepare(raw_text: str, language_id: str, complete: CompleteFn) -> LessonSubjectInput:
    result = build_prepare_graph(complete).invoke(
        {"language_id": language_id, "raw_text": raw_text, "subject": {}}
    )
    return LessonSubjectInput.model_validate(result["subject"])


def run_buddy_turn(
    ongoing: OngoingConversation,
    latest_human: str,
    *,
    complete: CompleteFn,
    actors: dict[str, Actor],
) -> ElementSolutionModel:
    result = build_turn_graph(complete, actors).invoke(
        {
            "language_id": ongoing.language,
            "ongoing": ongoing.model_dump(),
            "latest_human": latest_human,
            "line": "",
            "emotion": "neutral",
            "solution": {},
        }
    )
    return ElementSolutionModel.model_validate(result["solution"])
