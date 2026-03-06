from django.db import models
#test
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


class SalesProduct(models.Model):
    """A row in the Sales / C3 Product Performance table (monthly goal)."""
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Product price")
    goal = models.PositiveIntegerField(default=1, help_text="Monthly sales goal")
    display_order = models.PositiveIntegerField(default=0)
    product_id = models.PositiveIntegerField(null=True, blank=True)

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
    date = models.DateField()
    amount = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-date', 'id']

    def __str__(self):
        return f"{self.product.name} on {self.date}: {self.amount}" 