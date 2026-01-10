def resolve_microstep_source(
    *,
    silenced: bool,
    model_rate_limited: bool,
    used_fallback: bool,
    raw_model_microstep: str | None,
    pre_category_microstep: str | None,
    final_microstep: str | None,
    guardrail_adjusted: bool,
) -> str:
    # Silence contract always wins
    if silenced:
        return "silence_contract"

    # Rate-limit should be explicit even if we later enforce category/guardrails
    if model_rate_limited:
        return "fallback_due_to_rate_limit"

    raw = (raw_model_microstep or "").strip()
    pre = (pre_category_microstep or "").strip()
    final = (final_microstep or "").strip()

    # If final exactly equals raw model output, it truly came from model
    if raw and final == raw:
        return "model"

    # If we used fallback pool at any point, call it fallback (even if category picked a fallback line)
    if used_fallback:
        return "fallback"

    # If we did not use fallback and final equals the category-selected microstep, it was category-enforced
    if pre and final == pre:
        return "category_enforced"

    # If guardrails replaced something, label it clearly
    if guardrail_adjusted:
        return "guardrail_replaced"

    # Last resort: model was used but something modified it
    return "model_adjusted"