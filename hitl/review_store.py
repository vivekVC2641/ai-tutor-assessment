import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.config import settings
from models.schemas import FullEvaluationResponse, ReviewRecord

logger = logging.getLogger(__name__)


def save_review(
    question: str,
    student_answer: str,
    ai_score: float,
    human_score: float | None,
    reviewer_id: str,
    reason_for_override: str,
    feedback: str,
) -> ReviewRecord:
    final_score = float(human_score) if human_score is not None else float(ai_score)
    override_applied = human_score is not None
    record = ReviewRecord(
        question=question,
        student_answer=student_answer,
        ai_score=ai_score,
        human_score=human_score,
        final_score=final_score,
        reviewer_id=reviewer_id,
        reason_for_override=reason_for_override,
        override_applied=override_applied,
        feedback=feedback,
        timestamp=datetime.now(timezone.utc),
    )

    file_path = Path(settings.review_store_file)
    data = _load_json_list(file_path)
    data.append(record.model_dump(mode="json"))
    file_path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
    logger.info("Saved review record. total_reviews=%s file=%s", len(data), file_path)
    return record


def get_review_stats() -> dict:
    file_path = Path(settings.review_store_file)
    data = _load_json_list(file_path)
    total_reviews = len(data)
    if total_reviews == 0:
        return _empty_review_stats()

    override_records = [r for r in data if r.get("human_score") is not None]
    override_count = len(override_records)
    avg_delta = 0.0
    if override_count:
        deltas = []
        for r in override_records:
            try:
                deltas.append(float(r["human_score"]) - float(r["ai_score"]))
            except (TypeError, ValueError, KeyError):
                logger.warning("Skipping invalid review delta row: %s", r)
        avg_delta = (sum(deltas) / len(deltas)) if deltas else 0.0
    return {
        "total_reviews": total_reviews,
        "override_count": override_count,
        "override_rate": override_count / total_reviews,
        "average_score_delta": avg_delta,
    }


def _empty_review_stats() -> dict:
    return {
        "total_reviews": 0,
        "override_count": 0,
        "override_rate": 0.0,
        "average_score_delta": 0.0,
    }


def _load_json_list(file_path: Path) -> list[dict]:
    if not file_path.exists():
        logger.info("Store file does not exist, using empty list. file=%s", file_path)
        return []
    try:
        raw = file_path.read_text(encoding="utf-8").strip()
        if not raw:
            logger.warning("Store file is empty, using empty list. file=%s", file_path)
            return []
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            logger.warning("Store file has invalid root type, using empty list. file=%s", file_path)
            return []
        valid_rows = [x for x in parsed if isinstance(x, dict)]
        if len(valid_rows) != len(parsed):
            logger.warning(
                "Store file had non-dict rows; filtered. file=%s kept=%s total=%s",
                file_path,
                len(valid_rows),
                len(parsed),
            )
        return valid_rows
    except json.JSONDecodeError:
        logger.exception("Store file contains invalid JSON, using empty list. file=%s", file_path)
        return []
    except OSError:
        logger.exception("Could not read store file, using empty list. file=%s", file_path)
        return []


def _save_json_list(file_path: Path, data: list[dict]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
    logger.info("Saved JSON list. file=%s rows=%s", file_path, len(data))


def create_evaluation_record(result: FullEvaluationResponse) -> str:
    eval_id = f"eval_{uuid4().hex[:12]}"
    payload = result.model_dump(mode="json")
    payload["evaluation_id"] = eval_id
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()

    file_path = Path(settings.evaluation_store_file)
    data = _load_json_list(file_path)
    data.append(payload)
    _save_json_list(file_path, data)
    logger.info("Created evaluation record. evaluation_id=%s", eval_id)
    return eval_id


def get_evaluation_record(evaluation_id: str) -> dict | None:
    file_path = Path(settings.evaluation_store_file)
    data = _load_json_list(file_path)
    for item in data:
        if item.get("evaluation_id") == evaluation_id:
            return item
    logger.info("Evaluation record not found. evaluation_id=%s", evaluation_id)
    return None


def update_evaluation_record(evaluation_id: str, updated_payload: dict) -> None:
    file_path = Path(settings.evaluation_store_file)
    data = _load_json_list(file_path)
    for idx, item in enumerate(data):
        if item.get("evaluation_id") == evaluation_id:
            updated_payload["evaluation_id"] = evaluation_id
            updated_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            data[idx] = updated_payload
            _save_json_list(file_path, data)
            logger.info("Updated evaluation record. evaluation_id=%s", evaluation_id)
            return
    logger.error("Failed to update evaluation record. evaluation_id=%s", evaluation_id)
    raise ValueError("Evaluation record not found")


def list_evaluation_records() -> list[dict]:
    file_path = Path(settings.evaluation_store_file)
    data = _load_json_list(file_path)
    data.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return data
