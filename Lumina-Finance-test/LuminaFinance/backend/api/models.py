from django.contrib.auth.hashers import check_password, make_password
from django.db import models


class UserAuth(models.Model):
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=128)
    display_name = models.CharField(max_length=80)
    base_currency = models.CharField(max_length=3, default="USD")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "User_Auth"

    def set_password(self, raw_password: str) -> None:
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password_hash)


class Category(models.Model):
    EXPENSE, INCOME = "EXPENSE", "INCOME"
    KIND_CHOICES = [(EXPENSE, "Expense"), (INCOME, "Income")]

    name = models.CharField(max_length=60, unique=True)
    kind = models.CharField(max_length=8, choices=KIND_CHOICES)

    class Meta:
        db_table = "Categories"


class AssetClass(models.Model):
    name = models.CharField(max_length=40, unique=True)

    class Meta:
        db_table = "Asset_Classes"


class Transaction(models.Model):
    user = models.ForeignKey(UserAuth, on_delete=models.CASCADE, db_column="user_id")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, db_column="category_id")
    amount = models.DecimalField(max_digits=19, decimal_places=4)
    txn_date = models.DateField()
    description = models.CharField(max_length=180, blank=True, null=True)
    is_recurring = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "Transactions"
        indexes = [
            models.Index(fields=["user", "-txn_date"], name="idx_txn_user_date"),
            models.Index(fields=["user", "category"], name="idx_txn_user_cat"),
        ]


class AssetPortfolio(models.Model):
    user = models.ForeignKey(UserAuth, on_delete=models.CASCADE, db_column="user_id")
    asset_class = models.ForeignKey(AssetClass, on_delete=models.PROTECT, db_column="asset_class_id")
    ticker = models.CharField(max_length=20)
    quantity = models.DecimalField(max_digits=19, decimal_places=4)
    cost_basis = models.DecimalField(max_digits=19, decimal_places=4)
    acquired_at = models.DateField()

    class Meta:
        db_table = "Asset_Portfolio"


class AssetPriceHistory(models.Model):
    asset = models.ForeignKey(AssetPortfolio, on_delete=models.CASCADE, db_column="asset_id")
    price = models.DecimalField(max_digits=19, decimal_places=4)
    recorded_at = models.DateTimeField()

    class Meta:
        db_table = "Asset_Price_History"


class ForecastSnapshot(models.Model):
    user = models.ForeignKey(UserAuth, on_delete=models.CASCADE, db_column="user_id")
    generated_at = models.DateTimeField(auto_now_add=True)
    horizon_months = models.PositiveSmallIntegerField(default=6)
    projected_spend = models.DecimalField(max_digits=19, decimal_places=4)
    projected_income = models.DecimalField(max_digits=19, decimal_places=4)
    runway_months = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    method = models.CharField(max_length=40)
    params = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "Forecast_Snapshots"
