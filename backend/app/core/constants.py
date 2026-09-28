"""Shared numeric constants that mirror the contract."""

# Fixed-point scale for unit price (contract PRICE_SCALE = 1e8).
PRICE_SCALE = 10**8


def price_to_float(scaled: int) -> float:
    """Convert a PRICE_SCALE-scaled unit price to a human float."""
    return scaled / PRICE_SCALE
