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
    # 1) Silence contract always wins
    if silenced:
        return "silence_contract"

    # 2) Rate-limit should be explicit (even if later enforcement happens)
    if model_rate_limited:
        return "fallback_due_to_rate_limit"

    raw = (raw_model_microstep or "").strip()
    pre = (pre_category_microstep or "").strip()
    final = (final_microstep or "").strip()

    # 3) If fallback pool was used at any point, label fallback (wins over adjusted/model)
    if used_fallback:
        return "fallback"

    # 4) Guardrails replacing content is a stronger signal than category enforcement
    if guardrail_adjusted:
        return "guardrail_replaced"

    # 5) If final exactly equals raw model output, it came from the model
    if raw and final == raw:
        return "model"

    # 6) If we didn't use fallback and final equals the category-selected microstep, it was enforced
    if pre and final == pre:
        return "category_enforced"

    # 7) Last resort: model was used but something modified it
    return "model_adjusted"