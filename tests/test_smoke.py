# tests/test_smoke.py

def test_runtime_imports():
    import agi.utils
    import agi.deepen_ai

def test_microstep_source_function():
    from agi.utils import resolve_microstep_source

    assert resolve_microstep_source(
        silenced=False,
        model_rate_limited=False,
        used_fallback=False,
        raw_model_microstep="Place one hand on your chest.",
        pre_category_microstep="Place one hand on your chest.",
        final_microstep="Place one hand on your chest.",
        guardrail_adjusted=False,
    ) == "model"