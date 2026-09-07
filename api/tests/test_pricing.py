from app.pricing import cost_usd


def test_charges_input_and_output_at_the_model_rates():
    assert cost_usd("claude-opus-5", input_tokens=1_000_000, output_tokens=0) == 5.0
    assert cost_usd("claude-opus-5", input_tokens=0, output_tokens=1_000_000) == 25.0


def test_cache_reads_are_cheaper_than_input_and_writes_dearer():
    read = cost_usd("claude-opus-5", input_tokens=0, output_tokens=0, cache_read_tokens=1_000_000)
    write = cost_usd("claude-opus-5", input_tokens=0, output_tokens=0, cache_write_tokens=1_000_000)
    assert read < 5.0 < write


def test_an_unknown_model_costs_zero_rather_than_guessing():
    assert cost_usd("some-other-model", input_tokens=1_000_000, output_tokens=1_000_000) == 0.0
