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


def fulfill_inventory_order(order):
    """Mark order delivered: increase stock and set date_received."""
    from .models import InventoryOrder

    if not order or order.status != InventoryOrder.STATUS_PENDING:
        return

    with transaction.atomic():
        row, _ = get_or_create_inventory_row(order.product, order.dealership)
        row.quantity = int(row.quantity) + int(order.quantity_requested)
        row.save(update_fields=["quantity", "last_updated"])

        order.status = InventoryOrder.STATUS_DELIVERED
        order.date_received = timezone.now()
        order.save(update_fields=["status", "date_received"])

