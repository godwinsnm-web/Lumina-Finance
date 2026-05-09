"""
Seed a single demo user with 6 months of habitual transactions, planted
outliers, and a multi-asset portfolio. Idempotent — safe to re-run.

    python manage.py seed_demo
"""

import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction as dbtxn
from django.utils import timezone as djtz

from api.models import (
    AssetClass, AssetPortfolio, AssetPriceHistory,
    Category, Transaction, UserAuth,
)

CATEGORIES = [
    ("Salary",        Category.INCOME),
    ("Dividends",     Category.INCOME),
    ("Rent",          Category.EXPENSE),
    ("Groceries",     Category.EXPENSE),
    ("Dining",        Category.EXPENSE),
    ("Transport",     Category.EXPENSE),
    ("Subscriptions", Category.EXPENSE),
    ("Travel",        Category.EXPENSE),
    ("Healthcare",    Category.EXPENSE),
    ("Other",         Category.EXPENSE),
]
ASSET_CLASSES = ["Cash", "Stocks", "Crypto", "Gold", "Bonds"]

# (ticker, asset_class, qty, cost_basis_per_unit, current_price_per_unit)
HOLDINGS = [
    ("USD",  "Cash",   Decimal("10607.00"), Decimal("1.0000"),    Decimal("1.0000")),
    ("NVDA", "Stocks", Decimal("12.4"),     Decimal("95.20"),     Decimal("103.43")),   # +8.6%
    ("AAPL", "Stocks", Decimal("48.0"),     Decimal("178.40"),    Decimal("182.10")),
    ("VOO",  "Stocks", Decimal("28.0"),     Decimal("428.00"),    Decimal("445.30")),
    ("BTC",  "Crypto", Decimal("0.142"),    Decimal("58400.00"),  Decimal("61120.00")),
    ("XAU",  "Gold",   Decimal("2.55"),     Decimal("2180.00"),   Decimal("2269.00")),
]

EXPENSE_DISTRIBUTION = [
    # (category_name, monthly_count_range, amount_range)
    ("Groceries",     (5, 8),  (40, 160)),
    ("Dining",        (4, 7),  (12, 95)),
    ("Transport",     (3, 6),  (8, 55)),
    ("Subscriptions", (3, 4),  (6, 28)),
    ("Healthcare",    (0, 2),  (15, 220)),
    ("Other",         (1, 3),  (10, 80)),
]


class Command(BaseCommand):
    help = "Seed reference data + a demo user with 6 months of transactions and a portfolio."

    @dbtxn.atomic
    def handle(self, *args, **opts):
        random.seed(7)

        for name, kind in CATEGORIES:
            Category.objects.get_or_create(name=name, defaults={"kind": kind})
        for name in ASSET_CLASSES:
            AssetClass.objects.get_or_create(name=name)

        user, _ = UserAuth.objects.get_or_create(
            email="ada@lumina.local",
            defaults={
                "password_hash": "",
                "display_name":  "Ada Lovelace",
                "base_currency": "USD",
            },
        )
        # Always (re)set the demo password so re-running the seeder is safe.
        user.set_password("demo1234")
        user.save(update_fields=["password_hash"])

        Transaction.objects.filter(user=user).delete()
        cats = {c.name: c for c in Category.objects.all()}

        today = djtz.now().date()
        first_of_this_month = today.replace(day=1)

        # ── 6 months of expense transactions ────────────────
        for m in range(6):
            month_start = (first_of_this_month - timedelta(days=m * 31)).replace(day=1)
            for cat_name, (lo, hi), (amt_lo, amt_hi) in EXPENSE_DISTRIBUTION:
                for _ in range(random.randint(lo, hi)):
                    Transaction.objects.create(
                        user=user,
                        category=cats[cat_name],
                        amount=Decimal(str(round(random.uniform(amt_lo, amt_hi), 2))),
                        txn_date=month_start + timedelta(days=random.randint(0, 27)),
                    )
            # rent: one recurring fixed line per month
            Transaction.objects.create(
                user=user, category=cats["Rent"],
                amount=Decimal("1450.00"),
                txn_date=month_start + timedelta(days=1),
                is_recurring=True, description="Rent",
            )
            # planted dining outlier — the "$1,850 dinner" the IQR filter must drop
            Transaction.objects.create(
                user=user, category=cats["Dining"],
                amount=Decimal("1850.00"),
                txn_date=month_start + timedelta(days=12),
                description="Anniversary dinner (outlier)",
            )
            # salary — one income line per month
            Transaction.objects.create(
                user=user, category=cats["Salary"],
                amount=Decimal("6200.00"),
                txn_date=month_start + timedelta(days=27),
                is_recurring=True, description="Salary",
            )

        # ── Portfolio + latest prices ───────────────────────
        AssetPortfolio.objects.filter(user=user).delete()
        ac = {a.name: a for a in AssetClass.objects.all()}
        now = djtz.now()
        for ticker, klass, qty, cost, price in HOLDINGS:
            asset = AssetPortfolio.objects.create(
                user=user, asset_class=ac[klass], ticker=ticker,
                quantity=qty, cost_basis=cost,
                acquired_at=today - timedelta(days=120),
            )
            AssetPriceHistory.objects.create(asset=asset, price=price, recorded_at=now)

        n_txn = Transaction.objects.filter(user=user).count()
        n_assets = AssetPortfolio.objects.filter(user=user).count()
        self.stdout.write(self.style.SUCCESS(
            f"Seeded {user.display_name}: {n_txn} transactions, {n_assets} holdings."
        ))
