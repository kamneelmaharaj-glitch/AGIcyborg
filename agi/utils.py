def resolve_microstep_dominance(
    *,
    silenced: bool,
    model_rate_limited: bool,
    used_fallback: bool,
    guardrail_adjusted: bool,
    pre_category_microstep: str | None,
    raw_model_microstep: str | None,
    final_microstep: str | None,
) -> str:
    """
    Dominance = what most clearly determined the FINAL microstep text.
    Preference order is based on observable equality (final==raw/pre) and hard overrides.
    """

    if silenced:
        return "silence_contract"

    final = (final_microstep or "").strip()
    pre = (pre_category_microstep or "").strip()
    raw = (raw_model_microstep or "").strip()

    # 1) Hard override always dominates the final step
    if guardrail_adjusted:
        return "guardrail"

    # 2) Category enforcement dominates when final matches pre-category (and differs from raw)
    if pre and final and final == pre and (not raw or final != raw):
        return "category"

    # 3) If the final equals the raw model step, model dominated (even if used_fallback was true for insight)
    if raw and final and final == raw:
        return "model"

    # 4) If rate-limited, we're effectively on fallback paths (no reliable raw signal)
    if model_rate_limited:
        return "fallback"

    # 5) If we know fallback was used and there's no raw match, fallback dominated
    if used_fallback:
        return "fallback"

    # 6) Otherwise: model contributed but was altered (shaping/reduction/etc.)
    return "model_adjusted"

def resolve_microstep_source(
    *,
    silenced: bool,
    model_rate_limited: bool,
    used_fallback: bool,
    raw_model_microstep: str | None = None,
    pre_category_microstep: str | None = None,
    final_microstep: str | None = None,
    category_adjusted: bool = False,
    guardrail_adjusted: bool = False,
    **_ignored: object,
) -> str:
    def _norm(s: str | None) -> str:
        return " ".join((s or "").strip().split()).rstrip(".")

    # 1) Silence always wins
    if silenced:
        return "silence_contract"

    # 2) Guardrail replacement wins next
    if guardrail_adjusted:
        return "guardrail_replaced"

    # 3) Rate limit explicit fallback
    if model_rate_limited:
        return "fallback_due_to_rate_limit"

    # 4) CATEGORY WINS (your choice A): if final matches the category microstep
    #    AND category_adjusted was applied, label as category_applied.
    if category_adjusted and _norm(final_microstep) and _norm(final_microstep) == _norm(pre_category_microstep):
        return "category_applied"

    # 5) Otherwise, fallback vs model
    if used_fallback:
        return "fallback"

    if _norm(final_microstep) and _norm(final_microstep) == _norm(raw_model_microstep):
        return "model"

    return "model_adjusted"