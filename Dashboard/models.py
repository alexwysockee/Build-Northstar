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

    class Meta:
        ordering = ["name"]

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
        """Sum of daily sales for the current month."""
        from django.db.models import Sum
        from django.utils import timezone
        now = timezone.now()
        total = self.dailysale_set.filter(
            date__year=now.year,
            date__month=now.month,
        ).aggregate(Sum('amount'))['amount__sum']
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
    """Request for more stock; pending until a manager marks delivered (stock increases)."""
    STATUS_PENDING = "pending"
    STATUS_DELIVERED = "delivered"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_DELIVERED, "Delivered"),
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

    class Meta:
        ordering = ["-date_requested", "-id"]

    @property
    def display_order_id(self):
        return f"{self.pk:04d}"

    def __str__(self):
        return f"Order {self.pk} {self.product.name} → {self.dealership.name}"