# Dashboard/forms.py
from django import forms
from django.core.exceptions import ValidationError

from .inventory_services import quantity_on_hand, user_home_dealership
from .models import Dealership, DailySale, InventoryOrder, Entry, Report, SalesProduct


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["text"]
        labels = {"text": "Report title"}
        widgets = {
            "text": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Report title"}
            )
        }


class EntryForm(forms.ModelForm):
    class Meta:
        model = Entry
        fields = ["text"]
        labels = {"text": "Entry"}
        widgets = {
            "text": forms.Textarea(
                attrs={"class": "form-control", "rows": 4, "placeholder": "Enter entry text..."}
            )
        }


class SalesProductForm(forms.ModelForm):
    class Meta:
        model = SalesProduct
        fields = ["name", "price", "goal", "tracks_inventory"]
        labels = {
            "name": "Product name",
            "price": "Price",
            "goal": "Monthly goal",
            "tracks_inventory": "Physical inventory item (track stock)",
        }
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Product name"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "0.01"}),
            "goal": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "tracks_inventory": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class DailySaleForm(forms.ModelForm):
    class Meta:
        model = DailySale
        fields = ["product", "dealership", "date", "amount"]
        labels = {
            "product": "Product",
            "dealership": "Dealership",
            "date": "Date",
            "amount": "Amount",
        }
        widgets = {
            "product": forms.Select(attrs={"class": "form-select"}),
            "dealership": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self._user = user
        super().__init__(*args, **kwargs)

        from django.utils import timezone

        if not self.instance.pk and "date" not in (self.data or {}):
            self.initial.setdefault("date", timezone.now().date())

        # Scope dealership choices for non-staff users.
        can_pick_any = bool(
            self._user
            and self._user.is_authenticated
            and (
                self._user.is_staff
                or self._user.groups.filter(name__in=["Management", "Back Office"]).exists()
            )
        )
        if can_pick_any:
            self.fields["dealership"].queryset = Dealership.objects.all().order_by("name")
            return

        home = user_home_dealership(self._user) if self._user and self._user.is_authenticated else None
        if home:
            self.fields["dealership"].queryset = Dealership.objects.filter(pk=home.pk)
            if not self.instance.pk:
                self.initial.setdefault("dealership", home.pk)
        else:
            self.fields["dealership"].queryset = Dealership.objects.none()

    def clean(self):
        cleaned = super().clean()
        product = cleaned.get("product")
        dealership = cleaned.get("dealership")
        amount = cleaned.get("amount")

        if product is None or dealership is None or amount is None:
            return cleaned

        amount = int(amount)
        if getattr(product, "tracks_inventory", True):
            available = quantity_on_hand(product, dealership)
            # Editing: inventory was already reduced by the existing sale amount.
            if self.instance.pk:
                available += int(self.instance.amount or 0)
            if available < amount:
                raise ValidationError(
                    f"Insufficient physical inventory at {dealership.name}. "
                    f"Available {available}, requested {amount}."
                )

        return cleaned


class InventoryRequestForm(forms.ModelForm):
    """Submit an inventory replenishment request (pending)."""

    class Meta:
        model = InventoryOrder
        fields = ["product", "dealership", "quantity_requested", "notes"]
        labels = {
            "product": "Product",
            "dealership": "Dealership",
            "quantity_requested": "Quantity requested",
            "notes": "Notes (optional)",
        }
        widgets = {
            "product": forms.Select(attrs={"class": "form-select"}),
            "dealership": forms.Select(attrs={"class": "form-select"}),
            "quantity_requested": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self._user = user
        super().__init__(*args, **kwargs)

        # Only physical inventory items should be orderable.
        self.fields["product"].queryset = (
            SalesProduct.objects.filter(tracks_inventory=True).order_by("display_order", "id")
        )

        can_pick_any = bool(
            self._user
            and self._user.is_authenticated
            and (
                self._user.is_staff
                or self._user.groups.filter(name__in=["Management", "Back Office"]).exists()
            )
        )
        if can_pick_any:
            self.fields["dealership"].queryset = Dealership.objects.all().order_by("name")
            return

        home = user_home_dealership(self._user) if self._user and self._user.is_authenticated else None
        if home:
            self.fields["dealership"].queryset = Dealership.objects.filter(pk=home.pk)
            self.initial.setdefault("dealership", home.pk)
        else:
            # WIP fallback: if no assigned dealership exists, still show choices.
            self.fields["dealership"].queryset = Dealership.objects.all().order_by("name")
