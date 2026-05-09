import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction as dbtxn
from django.utils import timezone as djtz
import calendar

from api.models import (
    AssetClass, AssetPortfolio, AssetPriceHistory, UserAuth, Category, Transaction
)

ASSET_CLASSES = ["Cash", "Stocks", "Crypto", "Gold", "Bonds"]

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
    help = "Seed multiple fake users and one specific user with random portfolio and transaction data."

    @dbtxn.atomic
    def handle(self, *args, **opts):
        random.seed()
        
        # Ensure categories exist
        for name, kind in CATEGORIES:
            Category.objects.get_or_create(name=name, defaults={"kind": kind})

        # Ensure asset classes exist
        for name in ASSET_CLASSES:
            AssetClass.objects.get_or_create(name=name)

        ac = {a.name: a for a in AssetClass.objects.all()}
        cats = {c.name: c for c in Category.objects.all()}
        today = djtz.now().date()
        now = djtz.now()

        def create_random_transactions(user):
            Transaction.objects.filter(user=user).delete()
            first_of_this_month = today.replace(day=1)
            
            # Base salary for calculating realistic expenses (between 5,000 and 20,000)
            base_salary = Decimal(str(round(random.uniform(5000, 20000), 2)))
            
            # The actual recorded income is 6x the base salary
            monthly_salary = base_salary * 6

            # ── 6 months of expense transactions ────────────────
            for m in range(6):
                month_start = (first_of_this_month - timedelta(days=m * 31)).replace(day=1)
                
                days_in_month = calendar.monthrange(month_start.year, month_start.month)[1]
                
                # Monthly burn target is 25% to 30% of the ORIGINAL base salary
                burn_ratio = Decimal(str(round(random.uniform(0.25, 0.30), 4)))
                target_burn = base_salary * burn_ratio
                
                # Allocate 50-60% of the burn to rent
                rent_ratio = Decimal(str(round(random.uniform(0.50, 0.60), 4)))
                rent_amount = target_burn * rent_ratio
                remaining_burn = target_burn - rent_amount
                
                small_expenses = []
                # Make the number of transactions much more random
                for cat_name, (lo, hi), (amt_lo, amt_hi) in EXPENSE_DISTRIBUTION:
                    for _ in range(random.randint(lo, hi + 3)):
                        amt = random.uniform(amt_lo, amt_hi)
                        small_expenses.append({"category": cat_name, "amount": amt})
                
                # Planted dining outlier sometimes
                if random.random() > 0.5:
                    small_expenses.append({"category": "Dining", "amount": random.uniform(500, 1500)})
                
                total_small = sum(e["amount"] for e in small_expenses)
                
                # Scale small expenses to exactly match the remaining_burn
                if total_small > 0:
                    scale = float(remaining_burn) / total_small
                    for e in small_expenses:
                        e["amount"] = e["amount"] * scale

                # Rent transaction (on the 1st of the month)
                Transaction.objects.create(
                    user=user, category=cats["Rent"],
                    amount=round(rent_amount, 2),
                    txn_date=month_start + timedelta(days=0),
                    is_recurring=True, description="Rent",
                )
                
                # Scaled small expenses spread across the ENTIRE month
                for e in small_expenses:
                    Transaction.objects.create(
                        user=user,
                        category=cats[e["category"]],
                        amount=Decimal(str(round(e["amount"], 2))),
                        txn_date=month_start + timedelta(days=random.randint(0, days_in_month - 1)),
                    )

                # Salary income transaction (e.g. on the 25th, before the month ends)
                salary_day = min(25, days_in_month - 1)
                Transaction.objects.create(
                    user=user, category=cats["Salary"],
                    amount=round(monthly_salary, 2),
                    txn_date=month_start + timedelta(days=salary_day),
                    is_recurring=True, description="Salary",
                )


        # Helper to generate random portfolio
        def create_random_portfolio(user, total_value):
            AssetPortfolio.objects.filter(user=user).delete()
            num_assets = random.randint(3, 5)
            allocations = [random.random() for _ in range(num_assets)]
            total_alloc = sum(allocations)
            allocations = [a / total_alloc for a in allocations]
            
            for alloc in allocations:
                klass = random.choice(ASSET_CLASSES)
                value = total_value * Decimal(str(alloc))
                
                # generate random price between 10 and 1000
                price = Decimal(str(round(random.uniform(10, 1000), 2)))
                if klass == "Cash":
                    price = Decimal("1.00")
                
                qty = value / price
                cost_basis_per_unit = price * Decimal(str(round(random.uniform(0.8, 1.2), 2)))
                
                ticker = f"TICK{random.randint(100,999)}"
                if klass == "Cash": ticker = "USD"
                elif klass == "Crypto": ticker = random.choice(["BTC", "ETH", "SOL", "ADA"])
                elif klass == "Stocks": ticker = random.choice(["AAPL", "GOOG", "TSLA", "AMZN", "MSFT"])
                elif klass == "Gold": ticker = "XAU"
                elif klass == "Bonds": ticker = "BND"
                
                asset = AssetPortfolio.objects.create(
                    user=user, asset_class=ac[klass], ticker=ticker,
                    quantity=qty, cost_basis=cost_basis_per_unit,
                    acquired_at=today - timedelta(days=random.randint(10, 365)),
                )
                AssetPriceHistory.objects.create(asset=asset, price=price, recorded_at=now)


        # Create godwin user
        godwin_user, _ = UserAuth.objects.get_or_create(
            email="godwin.snm@gmail.com",
            defaults={
                "display_name": "Godwin",
                "base_currency": "USD",
            }
        )
        godwin_user.set_password("godwin123")
        godwin_user.save()
        
        # Portfolio greater than 500k
        godwin_random_value = Decimal(str(round(random.uniform(500001, 800000), 2)))
        create_random_portfolio(godwin_user, godwin_random_value)
        create_random_transactions(godwin_user)
        
        # Create multiple fake users
        for i in range(1, 11): # creating 10 fake users
            fake_user, _ = UserAuth.objects.get_or_create(
                email=f"fakeuser{i}@example.com",
                defaults={
                    "display_name": f"Fake User {i}",
                    "base_currency": "USD",
                }
            )
            fake_user.set_password("password123")
            fake_user.save()
            
            # random portfolio under 200k
            random_value = Decimal(str(round(random.uniform(10000, 199999), 2)))
            create_random_portfolio(fake_user, random_value)
            create_random_transactions(fake_user)
            
        self.stdout.write(self.style.SUCCESS("Successfully seeded godwin and fake users with portfolios and transactions."))
