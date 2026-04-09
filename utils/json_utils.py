import json
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


def parse_json_with_retries(call_llm: Callable[[], str], max_retries: int = 2) -> dict:
    """
    Parse JSON from an LLM response with retry support.
    """
    attempts = 0
    while attempts <= max_retries:
        raw = call_llm().strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Some providers/models occasionally return a JSON "fragment" (e.g. `"answer": "...", ...`)
            # without the outer braces even when instructed to return JSON.
            # Try to wrap it into an object before falling back to substring extraction.
            fragment = raw.strip()
            if fragment and not fragment.startswith("{") and '"answer"' in fragment:
                wrapped = "{\n" + fragment.strip().strip(",") + "\n}"
                try:
                    return json.loads(wrapped)
                except json.JSONDecodeError:
                    logger.warning("LLM returned JSON fragment; wrapping failed. Retrying.")

            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and start < end:
                candidate = raw[start : end + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    logger.warning("LLM returned invalid JSON candidate. Retrying.")
            else:
                logger.warning("LLM returned no JSON object. Retrying.")
        attempts += 1

    raise ValueError("Failed to parse valid JSON from LLM response after retries.")
