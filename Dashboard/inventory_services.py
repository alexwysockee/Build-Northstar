"""
Inventory helpers for the Dashboard app.

These functions handle:
  - inventory status labels (out/low/adequate)
  - looking up current on-hand quantities
  - adjusting inventory when sales are added/edited/deleted
  - fulfilling inventory orders (mark delivered -> increase stock)
"""

from django.db import transaction
from django.utils import timezone


LOW_STOCK_THRESHOLD = 5

# Leaderboard / alert list caps (dashboard)
TOP_SALES_LEADERBOARD_LIMIT = 10
LOW_STOCK_ALERT_LIMIT = 25


def user_can_view_all_inventory(user):
    """True if user may see inventory for every dealership (staff/superuser/Management)."""
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    return user.groups.filter(name="Management").exists()


def dealerships_for_inventory_scope(user):
    """
    Dealership list for inventory tables and low-stock alerts (matches views.inventory).
    """
    from .models import Dealership

    if user_can_view_all_inventory(user):
        return list(Dealership.objects.order_by("name"))
    home = user_home_dealership(user)
    return [home] if home else list(Dealership.objects.order_by("name"))


def low_stock_alert_rows(user, max_rows=LOW_STOCK_ALERT_LIMIT):
    """
    Rows where on-hand is low or out (same thresholds as the inventory page).
    Returns (rows, truncated) where each row is a dict with product, dealership,
    quantity, status_label, badge_variant.
    """
    from .models import SalesProduct

    physical = list(
        SalesProduct.objects.filter(tracks_inventory=True).order_by("display_order", "id")
    )
    dealerships = dealerships_for_inventory_scope(user)
    raw = []
    for deal in dealerships:
        for p in physical:
            qty = quantity_on_hand(p, deal)
            _key, status_label, badge_variant = inventory_status_tuple(qty)
            if badge_variant in ("danger", "warning"):
                raw.append(
                    {
                        "product": p,
                        "dealership": deal,
                        "quantity": qty,
                        "status_label": status_label,
                        "badge_variant": badge_variant,
                    }
                )

    def sort_key(item):
        sev = 0 if item["badge_variant"] == "danger" else 1
        return (sev, item["quantity"], item["dealership"].name, item["product"].name)

    raw.sort(key=sort_key)
    truncated = len(raw) > max_rows
    return raw[:max_rows], truncated


def inventory_status_tuple(quantity: int):
    """Return (key, label, bootstrap_badge_class_suffix) for quantity."""
    if quantity <= 0:
        return ("out", "Out of Stock", "danger")
    if quantity < LOW_STOCK_THRESHOLD:
        return ("low", "Low", "warning")
    return ("adequate", "Adequate", "success")


def user_home_dealership(user):
    """Return the user's assigned Dealership (or None)."""
    if not user or not user.is_authenticated:
        return None
    try:
        from Profile.models import UserProfile

        prof = UserProfile.objects.select_related("dealership").filter(user=user).first()
        return prof.dealership if prof else None
    except Exception:
        return None


def quantity_on_hand(product, dealership):
    """Return on-hand units for product+dealership. Does not create missing rows."""
    from .models import ProductInventory

    row = (
        ProductInventory.objects.filter(product=product, dealership=dealership)
        .only("quantity")
        .first()
    )
    return int(row.quantity) if row else 0


def get_or_create_inventory_row(product, dealership):
    """Return (row, created) for product+dealership; creates row at 0 if needed."""
    from .models import ProductInventory

    row, created = ProductInventory.objects.get_or_create(
        product=product,
        dealership=dealership,
        defaults={"quantity": 0},
    )
    return row, created


def apply_sale_delta(product, dealership, units_sold_delta: int):
    """
    Adjust inventory when daily sales change.

    Positive delta means "more units sold" -> decrease inventory.
    Negative delta means "sales removed/edited down" -> increase inventory.
    """
    if not product or not dealership or units_sold_delta == 0:
        return
    if not getattr(product, "tracks_inventory", True):
        return

    from .models import ProductInventory

    with transaction.atomic():
        row, _ = get_or_create_inventory_row(product, dealership)
        row.quantity = max(0, int(row.quantity) - int(units_sold_delta))
        row.save(update_fields=["quantity", "last_updated"])


def fulfill_inventory_order(order, user):
    """Mark order delivered: increase stock, set date_received and delivered_by."""
    from .models import InventoryOrder

    if not order or order.status != InventoryOrder.STATUS_PENDING:
        return

    with transaction.atomic():
        row, _ = get_or_create_inventory_row(order.product, order.dealership)
        row.quantity = int(row.quantity) + int(order.quantity_requested)
        row.save(update_fields=["quantity", "last_updated"])

        order.status = InventoryOrder.STATUS_DELIVERED
        order.date_received = timezone.now()
        order.delivered_by = user if user and user.is_authenticated else None
        order.save(update_fields=["status", "date_received", "delivered_by"])


def cancel_inventory_order(order, user):
    """Mark order cancelled: no stock change."""
    from .models import InventoryOrder

    if not order or order.status != InventoryOrder.STATUS_PENDING:
        return

    with transaction.atomic():
        order.status = InventoryOrder.STATUS_CANCELLED
        order.cancelled_at = timezone.now()
        order.cancelled_by = user if user and user.is_authenticated else None
        order.save(update_fields=["status", "cancelled_at", "cancelled_by"])

