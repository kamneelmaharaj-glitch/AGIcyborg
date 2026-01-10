from agi.utils import resolve_microstep_source


def test_source_model_when_final_equals_raw():
    assert resolve_microstep_source(
        silenced=False,
        model_rate_limited=False,
        used_fallback=False,
        raw_model_microstep="Set both feet flat on the floor.",
        pre_category_microstep="Set both feet flat on the floor.",
        final_microstep="Set both feet flat on the floor.",
        guardrail_adjusted=False,
    ) == "model"


def test_source_category_enforced_when_final_equals_pre_category():
    assert resolve_microstep_source(
        silenced=False,
        model_rate_limited=False,
        used_fallback=False,
        raw_model_microstep="Place your hand on your heart and feel its rhythm.",
        pre_category_microstep="Place one hand on your abdomen.",
        final_microstep="Place one hand on your abdomen.",
        guardrail_adjusted=False,
    ) == "category_enforced"


def test_source_guardrail_replaced_when_guardrail_adjusted():
    assert resolve_microstep_source(
        silenced=False,
        model_rate_limited=False,
        used_fallback=False,
        raw_model_microstep="Take a big breath and hold it.",
        pre_category_microstep="Breathe slowly for ten seconds.",
        final_microstep="Place both hands on your thighs.",
        guardrail_adjusted=True,
    ) == "guardrail_replaced"

def test_source_silence_contract_when_silenced():
    assert resolve_microstep_source(
        silenced=True,
        model_rate_limited=False,
        used_fallback=False,
        raw_model_microstep="Anything",
        pre_category_microstep="Anything",
        final_microstep="Anything",
        guardrail_adjusted=False,
    ) == "silence_contract"


def test_source_fallback_due_to_rate_limit_when_rate_limited():
    assert resolve_microstep_source(
        silenced=False,
        model_rate_limited=True,
        used_fallback=True,
        raw_model_microstep="",
        pre_category_microstep="Set both feet flat on the floor.",
        final_microstep="Set both feet flat on the floor.",
        guardrail_adjusted=False,
    ) == "fallback_due_to_rate_limit"


def test_source_fallback_when_used_fallback_and_not_rate_limited():
    assert resolve_microstep_source(
        silenced=False,
        model_rate_limited=False,
        used_fallback=True,
        raw_model_microstep="",
        pre_category_microstep="Set both feet flat on the floor.",
        final_microstep="Set both feet flat on the floor.",
        guardrail_adjusted=False,
    ) == "fallback"

# -----------------------------
# Manual runner (python -m ...)
# -----------------------------
def main():
    print("RUNNING: deepen microstep source tests")

    test_source_model_when_final_equals_raw()
    test_source_category_enforced_when_final_equals_pre_category()
    test_source_guardrail_replaced_when_guardrail_adjusted()

    print("PASS: all microstep source tests passed.")


if __name__ == "__main__":
    main()