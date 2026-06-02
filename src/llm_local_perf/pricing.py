"""Token price helpers for cloud-LLM cost comparisons."""

# Claude's public Sonnet-tier output pricing is commonly quoted at $15 per
# million output tokens. The local estimate is a generation-throughput number,
# so compare it to output-token cost rather than input-token cost.
CLAUDE_OUTPUT_USD_PER_MILLION_TOKENS = 15.00
CLAUDE_PRICE_LABEL = "Claude output-token equivalent"
HOURS_PER_YEAR = 365 * 24


def estimate_claude_output_cost(tokens: int | float) -> float:
    """Return the estimated USD cost for the same number of Claude output tokens."""
    return (float(tokens) / 1_000_000) * CLAUDE_OUTPUT_USD_PER_MILLION_TOKENS


def estimate_hourly_claude_output_cost(yearly_tokens: int | float) -> float:
    """Return the estimated hourly USD cost for an annual token estimate."""
    return estimate_claude_output_cost(yearly_tokens) / HOURS_PER_YEAR


def format_usd(amount: int | float) -> str:
    """Format a USD amount with cents and thousands separators."""
    return f"${float(amount):,.2f}"
