from fastapi import APIRouter, HTTPException
import logging

from hitl.review_store import (
    create_evaluation_record,
    get_evaluation_record,
    get_review_stats,
    save_review,
    update_evaluation_record,
)
from models.schemas import (
    AnswerRequest,
    AskRequest,
    AskResponse,
    FullEvaluationResponse,
    IngestRequest,
    IngestResponse,
    ReviewRequest,
    ReviewStatsResponse,
)
from app.config import settings
from orchestrator.indexing import ingest_and_index
from orchestrator.pipeline import run_pipeline
from rag.retriever import INDEX_MISSING_ERROR
from uuid import uuid4

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ingest", response_model=IngestResponse)
def ingest_document(payload: IngestRequest) -> IngestResponse:
    try:
        logger.info("Ingest request received. file_path=%s", payload.file_path)
        result = ingest_and_index(file_path=payload.file_path)
        logger.info(
            "Ingest completed. file_path=%s chunks=%s index_created=%s",
            result.get("file_path"),
            result.get("chunks"),
            result.get("index_created"),
        )
        return IngestResponse(**result)
    except Exception as exc:
        logger.exception("Ingest failed. file_path=%s reason=%s", payload.file_path, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/ask", response_model=AskResponse)
def ask_question(payload: AskRequest) -> AskResponse:
    try:
        logger.info("Ask request received. question=%s", payload.question)
        result = run_pipeline(question=payload.question)
        return AskResponse(
            question=result.question,
            tutor_answer=result.tutor_answer,
            sources=result.sources,
            used_chunks=result.used_chunks,
            confidence=result.confidence,
            follow_up_hint=result.follow_up_hint,
            unsupported_claims=result.unsupported_claims,
        )
    except FileNotFoundError as exc:
        if str(exc) == INDEX_MISSING_ERROR:
            raise HTTPException(status_code=400, detail=INDEX_MISSING_ERROR) from exc
        logger.exception("Ask failed with file error. reason=%s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Ask failed. reason=%s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/answer", response_model=FullEvaluationResponse)
def evaluate_student_answer(payload: AnswerRequest) -> FullEvaluationResponse:
    try:
        logger.info("Answer request received. question=%s", payload.question)
        result = run_pipeline(question=payload.question, student_answer=payload.student_answer)
        # Minimal output required by user: score + feedback.
        # We still compute confidence internally, but we only surface status for UI.
        ai_score = float(result.evaluation.score) if result.evaluation else 0.0
        feedback = str(result.evaluation.feedback) if result.evaluation else "Not enough grounded context to evaluate."
        confidence = float(result.evaluation.confidence) if result.evaluation else 0.0
        status = "pending_review" if confidence < settings.confidence_threshold else "finalized"
        clipped_score = max(0.0, min(1.0, ai_score))

        response = FullEvaluationResponse(
            evaluation_id="",
            session_id=payload.session_id or f"sess_{uuid4().hex[:8]}",
            question_id=f"q_{uuid4().hex[:8]}",
            question=payload.question,
            student_answer=payload.student_answer,
            ai_answer=result.tutor_answer,
            sources=result.sources,
            used_chunks=result.used_chunks,
            ai_score=clipped_score,
            final_score=clipped_score,
            feedback=feedback,
            decision_source="ai",
            status=status,
        )
        evaluation_id = create_evaluation_record(response)
        response.evaluation_id = evaluation_id
        logger.info("Answer evaluation completed. evaluation_id=%s status=%s", evaluation_id, status)
        return response
    except FileNotFoundError as exc:
        if str(exc) == INDEX_MISSING_ERROR:
            raise HTTPException(status_code=400, detail=INDEX_MISSING_ERROR) from exc
        logger.exception("Answer failed with file error. reason=%s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Answer failed. reason=%s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/review", response_model=FullEvaluationResponse)
def review_with_human_override(payload: ReviewRequest) -> FullEvaluationResponse:
    try:
        record = get_evaluation_record(payload.evaluation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Evaluation record not found")

        existing = FullEvaluationResponse(**record)
        action = payload.action.lower().strip()
        if action not in {"approve", "override"}:
            raise HTTPException(status_code=400, detail="action must be approve or override")

        if action == "override":
            if payload.human_score is None:
                raise HTTPException(status_code=400, detail="human_score is required for override")
            existing.final_score = max(0.0, min(1.0, float(payload.human_score)))
            existing.feedback = payload.feedback.strip() or existing.feedback
            existing.decision_source = "human"
            override_reason = payload.reason_for_override or "manual_override"
        else:
            existing.final_score = existing.ai_score
            existing.feedback = payload.feedback.strip() or existing.feedback
            existing.decision_source = "ai"
            override_reason = "approved_ai_evaluation"

        existing.status = "finalized"
        update_evaluation_record(payload.evaluation_id, existing.model_dump(mode="json"))

        # Keep review analytics for assessment showcase.
        _ = save_review(
            question=existing.question,
            student_answer=existing.student_answer,
            ai_score=existing.ai_score,
            human_score=(existing.final_score if action == "override" else None),
            reviewer_id=payload.reviewer_id,
            reason_for_override=override_reason,
            feedback=existing.feedback,
        )
        logger.info(
            "Review submitted. evaluation_id=%s action=%s final_score=%.2f",
            payload.evaluation_id,
            action,
            existing.final_score,
        )
        return existing
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Review failed. evaluation_id=%s reason=%s", payload.evaluation_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/review/stats", response_model=ReviewStatsResponse)
def review_stats() -> ReviewStatsResponse:
    try:
        return ReviewStatsResponse(**get_review_stats())
    except Exception as exc:
        logger.exception("Review stats failed. reason=%s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/evaluation/{evaluation_id}", response_model=FullEvaluationResponse)
def get_evaluation(evaluation_id: str) -> FullEvaluationResponse:
    try:
        record = get_evaluation_record(evaluation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Evaluation record not found")
        try:
            return FullEvaluationResponse(**record)
        except Exception as exc:
            # Fallback for older/stale records: return a safe minimal response if possible.
            logger.warning("Evaluation record shape mismatch. evaluation_id=%s reason=%s", evaluation_id, exc)
            return FullEvaluationResponse(
                evaluation_id=str(record.get("evaluation_id", evaluation_id)),
                session_id=str(record.get("session_id", "unknown")),
                question_id=str(record.get("question_id", "unknown")),
                question=str(record.get("question", "")),
                student_answer=str(record.get("student_answer", "")),
                ai_answer=str(record.get("ai_answer", "")),
                sources=list(record.get("sources", [])),
                used_chunks=list(record.get("used_chunks", [])),
                ai_score=float(record.get("ai_score", 0.0)),
                final_score=float(record.get("final_score", record.get("ai_score", 0.0))),
                feedback=str(record.get("feedback", "No feedback available.")),
                decision_source=str(record.get("decision_source", "ai")),
                status=str(record.get("status", "finalized")),
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Get evaluation failed. evaluation_id=%s reason=%s", evaluation_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
