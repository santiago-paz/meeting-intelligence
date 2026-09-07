"""USD per million tokens, Anthropic list prices as of September 2026.

Cost is derived from the token counts the API reports and the model that
actually served the request, never from string-length estimates. An unknown
model costs zero rather than a made-up number; the trace still records it.
"""

PRICES_PER_MILLION = {
    "claude-opus-5": {"input": 5.00, "output": 25.00, "cache_read": 0.50, "cache_write": 6.25},
    "claude-sonnet-5": {"input": 2.00, "output": 10.00, "cache_read": 0.20, "cache_write": 2.50},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00, "cache_read": 0.10, "cache_write": 1.25},
}


def cost_usd(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    prices = next((p for name, p in PRICES_PER_MILLION.items() if model.startswith(name)), None)
    if prices is None:
        return 0.0
    total = (
        input_tokens * prices["input"]
        + output_tokens * prices["output"]
        + cache_read_tokens * prices["cache_read"]
        + cache_write_tokens * prices["cache_write"]
    )
    return round(total / 1_000_000, 6)
