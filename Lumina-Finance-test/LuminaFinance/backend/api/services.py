"""
Forecast engine + portfolio valuation helpers.

`SavingsForecaster` runs the IQR-filtered MA3 pipeline on raw transaction rows,
either supplied directly (tests, scripts) or pulled from the ORM via
`from_django(user_id, balance)`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from statistics import quantiles
from typing import Iterable


@dataclass(frozen=True)
class TxnRow:
    category_id: int
    amount: Decimal
    txn_date: date


@dataclass
class ForecastResult:
    projected_monthly_spend: Decimal
    projected_horizon_spend: Decimal
    runway_months: Decimal | None
    kept_count: int
    dropped_count: int
    method: str = "MA3_IQR_FILTER"
    params: dict = field(default_factory=dict)


class SavingsForecaster:
    HORIZON = 6
    LOOKBACK_MONTHS = 6
    MA_WINDOW = 3

    def __init__(self, txns: Iterable[TxnRow], current_balance: Decimal):
        self.txns = list(txns)
        self.balance = current_balance

    def _filter_anomalies(self, txns: list[TxnRow]) -> tuple[list[TxnRow], int]:
        by_cat: dict[int, list[TxnRow]] = defaultdict(list)
        for t in txns:
            by_cat[t.category_id].append(t)

        kept: list[TxnRow] = []
        dropped = 0
        for cat_txns in by_cat.values():
            amounts = sorted(float(t.amount) for t in cat_txns)
            if len(amounts) < 4:
                kept.extend(cat_txns)
                continue
            q1, _, q3 = quantiles(amounts, n=4)
            ceiling = q3 + 1.5 * (q3 - q1)
            for t in cat_txns:
                if float(t.amount) <= ceiling:
                    kept.append(t)
                else:
                    dropped += 1
        return kept, dropped

    def _moving_average(self, txns: list[TxnRow]) -> Decimal:
        monthly: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal("0"))
        for t in txns:
            monthly[(t.txn_date.year, t.txn_date.month)] += t.amount

        ordered = sorted(monthly.items())[-self.LOOKBACK_MONTHS:]
        if not ordered:
            return Decimal("0")
        window = [v for _, v in ordered[-self.MA_WINDOW:]]
        return sum(window, Decimal("0")) / Decimal(len(window))

    def run(self) -> ForecastResult:
        clean, dropped = self._filter_anomalies(self.txns)
        monthly = self._moving_average(clean).quantize(Decimal("0.0001"))
        runway = (self.balance / monthly).quantize(Decimal("0.01")) if monthly > 0 else None
        return ForecastResult(
            projected_monthly_spend=monthly,
            projected_horizon_spend=(monthly * self.HORIZON).quantize(Decimal("0.0001")),
            runway_months=runway,
            kept_count=len(clean),
            dropped_count=dropped,
            params={
                "horizon_months": self.HORIZON,
                "lookback_months": self.LOOKBACK_MONTHS,
                "ma_window": self.MA_WINDOW,
            },
        )

    @classmethod
    def from_django(cls, user_id: int, current_balance: Decimal) -> "SavingsForecaster":
        from .models import Transaction
        cutoff = date.today().replace(day=1) - timedelta(days=cls.LOOKBACK_MONTHS * 31)
        rows = (Transaction.objects
                .filter(user_id=user_id, category__kind="EXPENSE", txn_date__gte=cutoff)
                .values_list("category_id", "amount", "txn_date"))
        return cls((TxnRow(c, a, d) for c, a, d in rows), current_balance)


# ── Portfolio valuation ─────────────────────────────────────
def valuate_portfolio(user_id: int) -> tuple[Decimal, list[dict]]:
    """Return (total_value, per-asset rows). Latest price wins; cash uses cost basis."""
    from django.db.models import OuterRef, Subquery, F
    from .models import AssetPortfolio, AssetPriceHistory

    latest_price = (AssetPriceHistory.objects
                    .filter(asset_id=OuterRef("pk"))
                    .order_by("-recorded_at")
                    .values("price")[:1])

    rows = (AssetPortfolio.objects
            .filter(user_id=user_id)
            .annotate(latest_price=Subquery(latest_price))
            .values("id", "ticker", "quantity", "cost_basis",
                    "asset_class__name", "latest_price"))

    out: list[dict] = []
    total = Decimal("0")
    for r in rows:
        price = r["latest_price"] or r["cost_basis"]
        value = (Decimal(price) * Decimal(r["quantity"])).quantize(Decimal("0.0001"))
        total += value
        out.append({
            "ticker": r["ticker"],
            "asset_class": r["asset_class__name"],
            "quantity": Decimal(r["quantity"]),
            "value": value,
            "cost_basis": Decimal(r["cost_basis"]),
            "current_price": Decimal(price),
        })
    return total, out
