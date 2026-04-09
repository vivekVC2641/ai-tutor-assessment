import logging

from app.config import settings
from app.llm_client import get_chat_client
from app.prompt_templates import EVALUATOR_PROMPTS
from utils.json_utils import parse_json_with_retries

logger = logging.getLogger(__name__)


def _to_score(value: object) -> float:
    # Normalize model output into the API's expected score range [0.0, 1.0].
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, score))


def evaluate_answer(question: str, context: str, student_answer: str) -> dict:
    client, chat_model = get_chat_client()
    template = EVALUATOR_PROMPTS.get(settings.prompt_version, EVALUATOR_PROMPTS["v1"])
    prompt = template.format(
        question=question, context=context, student_answer=student_answer
    )
    logger.info("Evaluator input prepared for question: %s", question)

    def _call_llm() -> str:
        # Force JSON mode so downstream parsing and schema mapping stay stable.
        completion = client.chat.completions.create(
            model=chat_model,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        content = completion.choices[0].message.content or "{}"
        logger.info("Evaluator output raw: %s", content)
        return content

    # Retry wrapper handles malformed/partial JSON occasionally returned by providers.
    parsed = parse_json_with_retries(_call_llm, max_retries=2)
    return {
        "score": _to_score(parsed.get("score", 0.0)),
        "feedback": str(parsed.get("feedback", "Improve conceptual accuracy and depth.")),
        "confidence": _to_score(parsed.get("confidence", 0.0)),
    }
