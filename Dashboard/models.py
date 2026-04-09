from django.conf import settings
from django.db import models


# Create your models here.

class Report(models.Model):
    # A Report the user is looking at
    text = models.CharField(max_length=200)
    date_added = models.DateTimeField(auto_now_add=True) 

    def __str__(self):
        # Return a string representation of the model
        return self.text


class Entry(models.Model):
    # Information and link to a Report
    Report = models.ForeignKey(Report, on_delete=models.CASCADE)
    text = models.TextField()
    date_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Entries'

    def __str__(self):
        # Return a string representation of the model
        return f"{self.text[:50]}..."


class EntryDocument(models.Model):
    """PDF documents attached to an entry."""
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE, related_name="documents")
    file = models.FileField(upload_to="entry_docs/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at", "-id"]

    def __str__(self):
        return f"Document for entry {self.entry_id}"


class Dealership(models.Model):
    """A dealership location. Inventory and orders are scoped per dealership."""
    name = models.CharField(max_length=200)
    badge_css_class = models.CharField(
        max_length=80,
        default="bg-dark",
        help_text="Bootstrap/extra CSS classes for this dealership's badge (navbar, user list).",
    )
    is_default_home = models.BooleanField(
        default=False,
        help_text="If True, new user group edits default to this dealership when none is set.",
    )

    class Meta:
        ordering = ["name"]

    def resolved_badge_css_class(self) -> str:
        """CSS classes for colored dealership pill (navbar + Users). DB value wins; else infer from name."""
        raw = (self.badge_css_class or "").strip()
        if raw.startswith("ns-badge-dealership-"):
            return raw
        name = (self.name or "").lower()
        if "mississauga" in name:
            return "ns-badge-dealership-mississauga"
        if "toronto" in name:
            return "ns-badge-dealership-toronto"
        if "edmonton" in name:
            return "ns-badge-dealership-edmonton"
        if "lachute" in name:
            return "ns-badge-dealership-lachute"
        if "calgary" in name:
            return "ns-badge-dealership-calgary"
        return raw

    def chart_color_hex(self) -> str:
        """Bar/legend color for charts; matches static/css/theme.css dealership badges."""
        key = self.resolved_badge_css_class()
        mapping = {
            "ns-badge-dealership-mississauga": "#0976f0",
            "ns-badge-dealership-toronto": "#001f3f",
            "ns-badge-dealership-edmonton": "#ea580c",
            "ns-badge-dealership-calgary": "#ef4444",
            "ns-badge-dealership-lachute": "#7f1d1d",
            "ns-badge-navy": "#001f3f",
            "ns-badge-c3-toronto": "#001f3f",
        }
        return mapping.get(key, "#495057")

    def __str__(self):
        return self.name


class SalesProduct(models.Model):
    """A row in the Sales / C3 Product Performance table (monthly goal)."""
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Product price")
    goal = models.PositiveIntegerField(default=1, help_text="Monthly sales goal")
    display_order = models.PositiveIntegerField(default=0)
    product_id = models.PositiveIntegerField(null=True, blank=True)
    tracks_inventory = models.BooleanField(
        default=True,
        help_text="If False (e.g. warranties), item is excluded from inventory and stock checks.",
    )

    class Meta:
        ordering = ['display_order', 'id']

    def __str__(self):
        return self.name

    def sales_this_month(self):
        """Sum of daily sales for the current calendar month (TIME_ZONE)."""
        from django.db.models import Sum
        from django.utils import timezone

        d = timezone.localdate()
        total = self.dailysale_set.filter(
            date__year=d.year,
            date__month=d.month,
        ).aggregate(Sum("amount"))["amount__sum"]
        return total or 0

    @property
    def goal_pct(self):
        if self.goal <= 0:
            return None
        total = self.sales_this_month()
        return round((total / self.goal) * 100)


class DailySale(models.Model):
    """Daily sales amount for a product (counts toward monthly total)."""
    product = models.ForeignKey(SalesProduct, on_delete=models.CASCADE)
    dealership = models.ForeignKey(Dealership, on_delete=models.CASCADE, related_name="daily_sales")
    date = models.DateField()
    amount = models.PositiveIntegerField(default=0)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_sales_entered",
    )

    class Meta:
        ordering = ['-date', 'id']

    def __str__(self):
        return f"{self.product.name} @ {self.dealership.name} on {self.date}: {self.amount}"


class ProductInventory(models.Model):
    """On-hand quantity for one physical product at one dealership (unique pair)."""
    product = models.ForeignKey(SalesProduct, on_delete=models.CASCADE, related_name="inventory_levels")
    dealership = models.ForeignKey(Dealership, on_delete=models.CASCADE, related_name="inventory_levels")
    quantity = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "dealership"],
                name="unique_product_dealership_inventory",
            ),
        ]
        ordering = ["dealership__name", "product__display_order", "product__id"]

    def __str__(self):
        return f"{self.product.name} @ {self.dealership.name}: {self.quantity}"


class InventoryOrder(models.Model):
    """Request for more stock; pending until delivered (stock up) or cancelled (no stock change)."""
    STATUS_PENDING = "pending"
    STATUS_DELIVERED = "delivered"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    product = models.ForeignKey(SalesProduct, on_delete=models.CASCADE, related_name="inventory_orders")
    dealership = models.ForeignKey(Dealership, on_delete=models.CASCADE, related_name="inventory_orders")
    quantity_requested = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_orders_submitted",
    )
    notes = models.TextField(blank=True)
    date_requested = models.DateTimeField(auto_now_add=True)
    date_received = models.DateTimeField(null=True, blank=True)
    delivered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fulfilled_inventory_orders",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cancelled_inventory_orders",
    )

    class Meta:
        ordering = ["-date_requested", "-id"]

    @property
    def display_order_id(self):
        return f"{self.pk:04d}"

    def __str__(self):
        return f"Order {self.pk} {self.product.name} → {self.dealership.name}"