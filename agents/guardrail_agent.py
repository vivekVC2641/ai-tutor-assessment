def run_guardrail_check(tutor_result: dict, retrieved_chunks: list[dict]) -> dict:
    """
    Lightweight answer grounding check.
    - If tutor explicitly says not found, allow it.
    - If no context retrieved, fail grounding.
    - If model itself flagged unsupported claims, fail grounding.
    """
    answer = str(tutor_result.get("answer", "")).strip().lower()
    unsupported_claims = tutor_result.get("unsupported_claims", [])
    if not isinstance(unsupported_claims, list):
        unsupported_claims = []

    if answer == "not found in provided material":
        return {"is_grounded": True, "reason": "safe_fallback"}
    if not retrieved_chunks:
        return {"is_grounded": False, "reason": "no_retrieved_context"}
    if unsupported_claims:
        return {"is_grounded": False, "reason": "unsupported_claims_present"}
    return {"is_grounded": True, "reason": "grounded"}
