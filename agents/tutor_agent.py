import logging

from app.llm_client import get_chat_client
from app.config import settings
from app.prompt_templates import TUTOR_PROMPTS
from utils.json_utils import parse_json_with_retries

logger = logging.getLogger(__name__)

def get_tutor_response(question: str, context: str) -> dict:
    client, chat_model = get_chat_client()
    template = TUTOR_PROMPTS.get(settings.prompt_version, TUTOR_PROMPTS["v1"])
    prompt = template.format(context=context, question=question)
    logger.info("Tutor input prepared for question: %s", question)

    last_raw: str = "{}"

    def _call_llm() -> str:
        nonlocal last_raw
        completion = client.chat.completions.create(
            model=chat_model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        content = completion.choices[0].message.content or "{}"
        last_raw = content
        logger.info("Tutor output raw: %s", content)
        return content

    try:
        parsed = parse_json_with_retries(_call_llm, max_retries=2)
    except Exception as exc:
        # If the provider returns malformed JSON, do not fail the whole API.
        # Fall back to using the raw output as the answer so the RAG system remains testable.
        logger.warning("Tutor JSON parsing failed; falling back to raw text. reason=%s", exc)
        return {
            "answer": (last_raw or "").strip() or "Not found in provided material",
            "sources": [],
            "confidence": 0.2,
            "follow_up_hint": None,
            "unsupported_claims": [],
        }
    # Defensive defaults
    confidence = float(parsed.get("confidence", 0.0))
    confidence = max(0.0, min(1.0, confidence))
    unsupported_claims = parsed.get("unsupported_claims", [])
    if not isinstance(unsupported_claims, list):
        unsupported_claims = []
    return {
        "answer": parsed.get("answer", "Not found in provided material"),
        "sources": parsed.get("sources", []),
        "confidence": confidence,
        "follow_up_hint": parsed.get("follow_up_hint"),
        "unsupported_claims": unsupported_claims,
    }
