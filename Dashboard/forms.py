# Dashboard/forms.py
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from .inventory_services import quantity_on_hand, user_home_dealership
from .models import (
    Claim,
    Dealership,
    DailySale,
    Inspection,
    InventoryOrder,
    Entry,
    Report,
    SalesProduct,
)


def daily_sales_queryset_for_claim_user(user):
    """DailySale rows the user may reference when filing a claim (same dealership scope as sales entry)."""
    qs = DailySale.objects.select_related("product", "dealership").order_by("-date", "-id")
    if not user or not user.is_authenticated:
        return DailySale.objects.none()

    can_pick_any = bool(
        user.is_staff
        or getattr(user, "is_superuser", False)
        or user.groups.filter(name__in=["Management", "Back Office"]).exists()
    )
    if can_pick_any:
        return qs

    home = user_home_dealership(user)
    if home:
        return qs.filter(dealership_id=home.pk)
    return DailySale.objects.none()


def resolve_daily_sale_from_ref(ref, queryset):
    """
    Match a single DailySale from user input (full order number, numeric pk, or NS-######).
    Returns (sale_or_none, error_message_or_none).
    """
    ref = (ref or "").strip()
    if not ref:
        return None, "Enter the order number from a recorded sale."

    exact = queryset.filter(order_number__iexact=ref).first()
    if exact:
        return exact, None

    digits = ref.lstrip("#").strip()
    if digits.isdigit():
        by_pk = queryset.filter(pk=int(digits)).first()
        if by_pk:
            return by_pk, None

    ru = ref.upper()
    if ru.startswith("NS-"):
        tail = ru[3:].strip()
        if tail.isdigit():
            by_pk = queryset.filter(pk=int(tail)).first()
            if by_pk:
                return by_pk, None

    q_norm = ref.lstrip("#").strip()
    q_filter = Q(order_number__icontains=ref)
    if q_norm != ref:
        q_filter |= Q(order_number__icontains=q_norm)
    matches = list(queryset.filter(q_filter).order_by("-date", "-id")[:10])
    if len(matches) == 0:
        return None, "No sale matches that reference for your access scope."
    if len(matches) > 1:
        return (
            None,
            "Multiple sales match. Use the full order number (e.g. NS-000042) or the numeric sale ID.",
        )
    return matches[0], None


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
                or getattr(self._user, "is_superuser", False)
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
                    f"This sale was not saved - not enough physical inventory at {dealership.name}. "
                    f"On hand: {available}. Amount entered: {amount}."
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
                or getattr(self._user, "is_superuser", False)
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


class ClaimForm(forms.ModelForm):
    """Submit a claim tied to an existing DailySale; only customer name, order reference, qty, and notes are free-form."""

    order_ref = forms.CharField(
        label="Order number",
        max_length=80,
        help_text="Must match a sale already recorded (e.g. NS-000042 from the Sales list).",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. NS-000042",
                "maxlength": 80,
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = Claim
        fields = ["customer_name", "quantity", "reason"]
        labels = {
            "customer_name": "Customer name",
            "quantity": "Quantity (for this claim)",
            "reason": "Notes",
        }
        widgets = {
            "customer_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. Jane Smith", "maxlength": 200}
            ),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "reason": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "Optional notes", "maxlength": 2000}
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        self._user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        order_ref = cleaned.get("order_ref")
        quantity = cleaned.get("quantity")
        qs = daily_sales_queryset_for_claim_user(self._user)
        sale, err = resolve_daily_sale_from_ref(order_ref, qs)
        if err:
            raise ValidationError({"order_ref": err})
        cleaned["daily_sale"] = sale

        sold = int(sale.amount or 0)
        if sold < 1:
            raise ValidationError(
                {"order_ref": "That sale has no units recorded; choose a sale with a quantity greater than zero."}
            )
        if quantity is not None:
            q = int(quantity)
            if q > sold:
                raise ValidationError(
                    {
                        "quantity": (
                            f"Cannot exceed units on this sale ({sold} for "
                            f"{sale.product.name} at {sale.dealership.name})."
                        )
                    }
                )
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.daily_sale = self.cleaned_data["daily_sale"]
        if commit:
            obj.save()
        return obj


class ClaimStatusForm(forms.Form):
    """Staff / Management / Back Office: change workflow status on an existing claim."""

    status = forms.ChoiceField(
        label="Status",
        choices=Claim.STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class InspectionForm(forms.ModelForm):
    """Record an inspection; optionally link a sale via order number (same resolution as claims)."""

    order_ref = forms.CharField(
        label="Order number (optional)",
        max_length=80,
        required=False,
        help_text="Link to a recorded sale (e.g. NS-000042). Leave blank if there is no sale to attach.",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. NS-000042",
                "maxlength": 80,
                "autocomplete": "off",
            }
        ),
    )

    RESULT_PASS = "pass"
    RESULT_FAIL = "fail"
    result = forms.ChoiceField(
        label="Result",
        choices=[
            (RESULT_PASS, "Pass"),
            (RESULT_FAIL, "Fail"),
        ],
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = Inspection
        fields = [
            "dealership",
            "product",
            "customer_name",
            "vin",
            "inspection_date",
            "odometer",
            "installer_name",
            "notes",
            "issue_damage",
            "issue_incomplete",
            "issue_warranty",
        ]
        labels = {
            "dealership": "Dealership",
            "product": "Product sold",
            "customer_name": "Customer",
            "vin": "VIN",
            "inspection_date": "Inspection date",
            "odometer": "Odometer",
            "installer_name": "Installer / employee",
            "notes": "Notes",
            "issue_damage": "Damage",
            "issue_incomplete": "Incomplete application",
            "issue_warranty": "Warranty concerns",
        }
        widgets = {
            "dealership": forms.Select(attrs={"class": "form-select"}),
            "product": forms.Select(attrs={"class": "form-select"}),
            "customer_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Customer name", "maxlength": 200}
            ),
            "vin": forms.TextInput(
                attrs={"class": "form-control font-monospace", "placeholder": "17-character VIN", "maxlength": 17}
            ),
            "inspection_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "odometer": forms.NumberInput(attrs={"class": "form-control", "min": 0, "placeholder": "Miles or km"}),
            "installer_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Who performed the inspection", "maxlength": 200}
            ),
            "notes": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "Optional notes"}
            ),
            "issue_damage": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "issue_incomplete": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "issue_warranty": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self._user = user
        super().__init__(*args, **kwargs)

        from django.utils import timezone

        if not self.instance.pk and "inspection_date" not in (self.data or {}):
            self.initial.setdefault("inspection_date", timezone.localdate())

        can_pick_any = bool(
            self._user
            and self._user.is_authenticated
            and (
                self._user.is_staff
                or getattr(self._user, "is_superuser", False)
                or self._user.groups.filter(name__in=["Management", "Back Office"]).exists()
            )
        )
        if can_pick_any:
            self.fields["dealership"].queryset = Dealership.objects.all().order_by("name")
        else:
            home = user_home_dealership(self._user) if self._user and self._user.is_authenticated else None
            if home:
                self.fields["dealership"].queryset = Dealership.objects.filter(pk=home.pk)
                if not self.instance.pk:
                    self.initial.setdefault("dealership", home.pk)
            else:
                self.fields["dealership"].queryset = Dealership.objects.none()

        self.fields["product"].queryset = SalesProduct.objects.all().order_by("display_order", "id")

        if not self.instance.pk and "result" not in (self.data or {}):
            self.initial.setdefault("result", self.RESULT_PASS)

    def clean_vin(self):
        vin = (self.cleaned_data.get("vin") or "").strip().upper()
        if len(vin) < 8:
            raise ValidationError("Enter a valid VIN (at least 8 characters).")
        if len(vin) > 17:
            raise ValidationError("VIN cannot exceed 17 characters.")
        return vin

    def clean(self):
        super().clean()
        order_ref = (self.cleaned_data.get("order_ref") or "").strip()
        result = self.cleaned_data.get("result")

        if result == self.RESULT_PASS:
            self.cleaned_data["passed"] = True
        elif result == self.RESULT_FAIL:
            self.cleaned_data["passed"] = False
        else:
            raise ValidationError({"result": "Choose pass or fail."})

        qs = daily_sales_queryset_for_claim_user(self._user)
        if order_ref:
            sale, err = resolve_daily_sale_from_ref(order_ref, qs)
            if err:
                raise ValidationError({"order_ref": err})
            self.cleaned_data["daily_sale"] = sale
            self.cleaned_data["dealership"] = sale.dealership
            self.cleaned_data["product"] = sale.product
        else:
            self.cleaned_data["daily_sale"] = None
            if not self.cleaned_data.get("dealership") or not self.cleaned_data.get("product"):
                raise ValidationError(
                    "Select a dealership and product, or enter an order number to link a recorded sale."
                )

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.daily_sale = self.cleaned_data.get("daily_sale")
        obj.passed = self.cleaned_data["passed"]
        if commit:
            obj.save()
        return obj
