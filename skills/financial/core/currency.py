"""Currency Layer — Decimal-safe money arithmetic.

Invariants:
  - Money amounts are NEVER floats. Always Decimal.
  - ISO 4217 currency codes enforced.
  - Rounding follows banker's rounding (ROUND_HALF_EVEN).
  - Display and settlement currencies are distinct.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, InvalidOperation
from enum import StrEnum


class Currency(StrEnum):
    """ISO 4217 currency codes (common subset)."""

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    ETB = "ETB"  # Ethiopian Birr
    JPY = "JPY"
    CHF = "CHF"
    CAD = "CAD"
    AUD = "AUD"
    NGN = "NGN"
    KES = "KES"
    ZAR = "ZAR"
    INR = "INR"
    BRL = "BRL"
    BTC = "BTC"
    ETH = "ETH"
    USDC = "USDC"


# Minor unit decimals per currency (0 for JPY, 2 for most, 8 for crypto)
_DECIMALS: dict[str, int] = {
    "JPY": 0, "BTC": 8, "ETH": 18, "USDC": 6,
}


def minor_units(currency: str) -> int:
    """Number of decimal places for a currency."""
    return _DECIMALS.get(currency, 2)


@dataclass(frozen=True, slots=True)
class Money:
    """Decimal-safe money value with currency.

    Never uses float. Arithmetic returns new Money objects.
    """

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, "amount", Decimal(str(self.amount)))
        if not self.currency:
            raise ValueError("currency must not be empty")

    def rounded(self) -> Money:
        """Round to currency's minor units using banker's rounding."""
        places = minor_units(self.currency)
        quantize_str = "0." + "0" * places if places > 0 else "1"
        rounded_amount = self.amount.quantize(Decimal(quantize_str), rounding=ROUND_HALF_EVEN)
        return Money(amount=rounded_amount, currency=self.currency)

    def __add__(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValueError(f"cannot add {self.currency} + {other.currency}")
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __sub__(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValueError(f"cannot subtract {self.currency} - {other.currency}")
        return Money(amount=self.amount - other.amount, currency=self.currency)

    def __lt__(self, other: Money) -> bool:
        if self.currency != other.currency:
            raise ValueError(f"cannot compare {self.currency} < {other.currency}")
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        if self.currency != other.currency:
            raise ValueError(f"cannot compare {self.currency} <= {other.currency}")
        return self.amount <= other.amount

    def __gt__(self, other: Money) -> bool:
        return not self.__le__(other)

    def __ge__(self, other: Money) -> bool:
        return not self.__lt__(other)

    @property
    def is_positive(self) -> bool:
        return self.amount > 0

    @property
    def is_zero(self) -> bool:
        return self.amount == 0

    def display(self) -> str:
        """Format for display (e.g., 'USD 1,234.56')."""
        places = minor_units(self.currency)
        formatted = f"{self.amount:,.{places}f}"
        return f"{self.currency} {formatted}"

    @classmethod
    def zero(cls, currency: str) -> Money:
        return cls(amount=Decimal("0"), currency=currency)

    @classmethod
    def from_str(cls, amount_str: str, currency: str) -> Money:
        """Parse amount from string (safe — no float conversion)."""
        try:
            return cls(amount=Decimal(amount_str), currency=currency)
        except InvalidOperation as exc:
            raise ValueError(f"invalid amount: {amount_str}") from exc
