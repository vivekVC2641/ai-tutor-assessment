import logging
from typing import Literal, TypedDict

from agents.guardrail_agent import run_guardrail_check
from agents.evaluator_agent import evaluate_answer
from agents.tutor_agent import get_tutor_response
from langgraph.graph import END, StateGraph
from models.schemas import EvaluationResponse, OrchestratorResponse
from rag.retriever import retrieve_top_chunks

logger = logging.getLogger(__name__)


class TutorGraphState(TypedDict, total=False):
    question: str
    student_answer: str | None
    retrieved: list[dict]
    context: str
    sources: list[str]
    tutor_result: dict
    guardrail: dict
    evaluation: dict | None
    debug: dict


def _normalize_source_ref(value: str) -> str:
    return str(value or "").strip().lower()


def _build_chunk_source_ref(chunk: dict) -> str:
    return f"{chunk.get('source', 'unknown')}::{chunk.get('section', 'unknown')}"


def _select_used_chunks(retrieved: list[dict], sources: list[str]) -> list[dict]:
    if not retrieved:
        return []

    normalized_sources = {_normalize_source_ref(s) for s in sources if str(s).strip()}
    if not normalized_sources:
        return retrieved

    used: list[dict] = []
    for item in retrieved:
        source_ref = _normalize_source_ref(_build_chunk_source_ref(item))
        section = _normalize_source_ref(str(item.get("section", "")))
        source = _normalize_source_ref(str(item.get("source", "")))
        if source_ref in normalized_sources or section in normalized_sources or source in normalized_sources:
            used.append(item)

    # If LLM sources are noisy/unmatched, return retrieved chunks for transparency.
    return used or retrieved


def _retrieve_node(state: TutorGraphState) -> TutorGraphState:
    retrieved = retrieve_top_chunks(state["question"], k=5)
    context = "\n\n".join(item.get("chunk", "") for item in retrieved)
    fallback_sources = list(
        {
            f"{item.get('source', 'unknown')}::{item.get('section', 'unknown')}"
            for item in retrieved
        }
    )
    logger.info("Retriever node returned %s chunks", len(retrieved))
    return {
        "retrieved": retrieved,
        "context": context,
        "sources": fallback_sources,
        "debug": {"retrieved_count": len(retrieved)},
    }


def _tutor_node(state: TutorGraphState) -> TutorGraphState:
    tutor_result = get_tutor_response(
        question=state["question"],
        context=state.get("context", ""),
    )
    return {"tutor_result": tutor_result}


def _guardrail_node(state: TutorGraphState) -> TutorGraphState:
    guardrail = run_guardrail_check(
        tutor_result=state.get("tutor_result", {}),
        retrieved_chunks=state.get("retrieved", []),
    )
    debug = state.get("debug", {})
    debug["guardrail"] = guardrail
    return {"guardrail": guardrail, "debug": debug}


def _should_continue(state: TutorGraphState) -> Literal["evaluate", "end"]:
    guardrail = state.get("guardrail", {})
    if not guardrail.get("is_grounded", False):
        return "end"
    if state.get("student_answer"):
        return "evaluate"
    return "end"


def _evaluate_node(state: TutorGraphState) -> TutorGraphState:
    eval_result = evaluate_answer(
        question=state["question"],
        context=state.get("context", ""),
        student_answer=state.get("student_answer", "") or "",
    )
    logger.info("Final evaluator score: %s", eval_result.get("score", 0.0))
    return {"evaluation": eval_result}


def _build_graph():
    graph = StateGraph(TutorGraphState)
    graph.add_node("retrieve", _retrieve_node)
    graph.add_node("tutor", _tutor_node)
    graph.add_node("guardrail", _guardrail_node)
    graph.add_node("evaluate", _evaluate_node)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "tutor")
    graph.add_edge("tutor", "guardrail")
    graph.add_conditional_edges(
        "guardrail",
        _should_continue,
        {"evaluate": "evaluate", "end": END},
    )
    graph.add_edge("evaluate", END)
    return graph.compile()


_GRAPH_APP = _build_graph()


def run_pipeline(question: str, student_answer: str | None = None) -> OrchestratorResponse:
    final_state = _GRAPH_APP.invoke(
        {"question": question, "student_answer": student_answer, "evaluation": None}
    )

    evaluation_payload = final_state.get("evaluation")
    evaluation = EvaluationResponse(**evaluation_payload) if evaluation_payload else None

    tutor_result = final_state.get("tutor_result", {})
    sources = tutor_result.get("sources") or final_state.get("sources", [])
    retrieved = final_state.get("retrieved", [])
    used_chunks = _select_used_chunks(retrieved=retrieved, sources=sources)

    return OrchestratorResponse(
        question=question,
        tutor_answer=tutor_result.get("answer", "Not found in provided material"),
        evaluation=evaluation,
        sources=sources,
        used_chunks=used_chunks,
        confidence=tutor_result.get("confidence", 0.0),
        follow_up_hint=tutor_result.get("follow_up_hint"),
        unsupported_claims=tutor_result.get("unsupported_claims", []),
        debug=final_state.get("debug", {}),
    )
