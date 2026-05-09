import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Transaction, UserAuth
from .services import SavingsForecaster, valuate_portfolio


def _q2(x: Decimal | None) -> float | None:
    return None if x is None else float(x.quantize(Decimal("0.01")))


def _current_user(request) -> UserAuth | None:
    uid = request.session.get("user_id")
    if uid is None:
        return None
    return UserAuth.objects.filter(pk=uid).first()


# ── Auth endpoints ──────────────────────────────────────────
@api_view(["POST"])
def login(request):
    email = (request.data.get("email") or "").strip().lower()
    password = request.data.get("password") or ""
    if not email or not password:
        return Response({"error": "email_and_password_required"}, status=status.HTTP_400_BAD_REQUEST)

    user = UserAuth.objects.filter(email__iexact=email).first()
    if user is None or not user.check_password(password):
        return Response({"error": "invalid_credentials"}, status=status.HTTP_401_UNAUTHORIZED)

    request.session["user_id"] = user.id
    request.session.set_expiry(60 * 60 * 24 * 14)  # 2 weeks
    return Response({"user": {"name": user.display_name, "email": user.email}})


@api_view(["POST"])
def register(request):
    email = (request.data.get("email") or "").strip().lower()
    password = request.data.get("password") or ""
    name = (request.data.get("name") or "").strip()
    
    if not email or not password or not name:
        return Response({"error": "all_fields_required"}, status=status.HTTP_400_BAD_REQUEST)
        
    if UserAuth.objects.filter(email__iexact=email).exists():
        return Response({"error": "email_taken"}, status=status.HTTP_400_BAD_REQUEST)
        
    user = UserAuth.objects.create(
        email=email,
        display_name=name,
        base_currency="USD"
    )
    user.set_password(password)
    user.save()
    
    request.session["user_id"] = user.id
    request.session.set_expiry(60 * 60 * 24 * 14)  # 2 weeks
    return Response({"user": {"name": user.display_name, "email": user.email}})


@api_view(["POST"])
def logout(request):
    request.session.flush()
    return Response({"ok": True})


@api_view(["GET"])
def me(request):
    user = _current_user(request)
    if user is None:
        return Response({"authenticated": False}, status=status.HTTP_401_UNAUTHORIZED)
    return Response({
        "authenticated": True,
        "user": {"name": user.display_name, "email": user.email, "currency": user.base_currency},
    })


# ── Dashboard ───────────────────────────────────────────────
@api_view(["GET"])
def dashboard(request):
    """
    Single denormalized payload for the dashboard. Frontend renders this directly;
    no client-side joins.
    """
    user = _current_user(request)
    if user is None:
        return Response({"error": "not_authenticated"}, status=status.HTTP_401_UNAUTHORIZED)

    total_balance, holdings = valuate_portfolio(user.id)
    forecast = SavingsForecaster.from_django(user.id, total_balance).run()
    burn = forecast.projected_monthly_spend

    # ── Allocation: aggregate value by asset class ──────────
    by_class: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for h in holdings:
        by_class[h["asset_class"]] += h["value"]

    allocation = []
    if total_balance > 0:
        for name, value in sorted(by_class.items(), key=lambda kv: -kv[1]):
            pct = (value / total_balance * 100).quantize(Decimal("0.01"))
            allocation.append({"label": name, "value": _q2(value), "pct": float(pct)})

    # ── Top mover: largest % gain (cost basis → current price) ──
    top = None
    top_pct = Decimal("-Infinity")
    for h in holdings:
        if h["asset_class"] == "Cash" or h["cost_basis"] <= 0:
            continue
        pct = (h["current_price"] - h["cost_basis"]) / h["cost_basis"] * 100
        if pct > top_pct:
            top_pct = pct
            top = h
    top_mover = None
    if top:
        top_mover = {
            "ticker": top["ticker"],
            "value": _q2(top["value"]),
            "quantity": float(top["quantity"]),
            "pct_change": float(top_pct.quantize(Decimal("0.01"))),
        }

    # ── 6-month forecast strip ──────────────────────────────
    today = date.today()
    strip = []
    running = total_balance
    for i in range(1, 7):
        running = (running - burn).quantize(Decimal("0.0001"))
        future_month = ((today.month - 1) + i) % 12 + 1   # 1..12
        strip.append({
            "month": calendar.month_abbr[future_month],
            "value": _q2(running),
            "delta": _q2(-burn),
        })

    # ── Recent transactions (last 30 days) ──────────────────
    from datetime import timedelta
    thirty_days_ago = date.today() - timedelta(days=30)
    recent = (Transaction.objects
              .filter(user=user, txn_date__gte=thirty_days_ago)
              .select_related("category")
              .order_by("-txn_date", "-id"))
    recent_payload = [{
        "id": t.id,
        "date": t.txn_date.isoformat(),
        "category": t.category.name,
        "kind": t.category.kind,
        "description": t.description or t.category.name,
        "amount": _q2(t.amount),
    } for t in recent]

    return Response({
        "user": {"name": user.display_name, "currency": user.base_currency, "email": user.email},
        "balance": {
            "total": _q2(total_balance),
            "trend_pct": 4.2,        # placeholder until we add a balance-history series
        },
        "burn": {
            "monthly": _q2(burn),
            "kept": forecast.kept_count,
            "dropped": forecast.dropped_count,
            "method": forecast.method,
        },
        "runway_months": _q2(forecast.runway_months),
        "allocation": allocation,
        "top_mover": top_mover,
        "forecast": strip,
        "recent_transactions": recent_payload,
    })


@api_view(["POST"])
def add_transaction(request):
    user = _current_user(request)
    if user is None:
        return Response({"error": "not_authenticated"}, status=status.HTTP_401_UNAUTHORIZED)
    
    desc = request.data.get("description", "")
    try:
        amount = Decimal(request.data.get("amount", "0"))
    except:
        amount = Decimal("0")
    
    kind = request.data.get("type", "EXPENSE")
    cat_name = request.data.get("category", "Other")
    
    from .models import Category, Transaction
    cat, _ = Category.objects.get_or_create(name=cat_name, defaults={"kind": kind})
    
    Transaction.objects.create(
        user=user,
        category=cat,
        amount=amount,
        txn_date=date.today(),
        description=desc
    )
    
    return Response({"ok": True})


@api_view(["DELETE"])
def delete_transaction(request, txn_id):
    user = _current_user(request)
    if user is None:
        return Response({"error": "not_authenticated"}, status=status.HTTP_401_UNAUTHORIZED)
    
    from .models import Transaction
    txn = Transaction.objects.filter(id=txn_id, user=user).first()
    if txn:
        txn.delete()
        return Response({"ok": True})
    return Response({"error": "not_found"}, status=status.HTTP_404_NOT_FOUND)
