from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q, Sum
from django.contrib import messages
from django.http import FileResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST
from .forms import ReportForm, EntryForm, SalesProductForm, DailySaleForm
from .forms import InventoryRequestForm, ClaimForm, ClaimStatusForm, InspectionForm
from .inventory_services import (
    apply_sale_delta,
    cancel_inventory_order,
    fulfill_inventory_order,
    get_or_create_inventory_row,
    quantity_on_hand,
    inventory_status_tuple,
    user_home_dealership,
)
from .scope import user_can_view_all_dealerships
from .models import (
    Claim,
    Dealership,
    DailySale,
    Entry,
    EntryDocument,
    Inspection,
    InspectionPhoto,
    InventoryOrder,
    ProductInventory,
    Report,
    SalesProduct,
)


def _staff_or_superuser(user):
    """Django admin staff or superuser (company-wide portal access)."""
    if not user.is_authenticated:
        return False
    return bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))


def _can_modify_daily_sales(user):
    """True if user is staff/superuser, Sales Rep, or Dealership User."""
    if not user.is_authenticated:
        return False
    if _staff_or_superuser(user):
        return True
    group_names = set(user.groups.values_list("name", flat=True))
    return "Sales Rep" in group_names or "Dealership User" in group_names


def _can_view_management_sales_archive(user):
    """All-time sales archive on Sales page: Management group, or staff/superuser."""
    if not user.is_authenticated:
        return False
    if _staff_or_superuser(user):
        return True
    return user.groups.filter(name="Management").exists()


MANAGEMENT_SALES_HISTORY_PER_PAGE = 75


def _is_management(user):
    """True if user is in the Management group."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name="Management").exists()


def _sales_month_today():
    """Calendar year/month in the active TIME_ZONE (matches typical date-picker 'today')."""
    d = timezone.localdate()
    return d.year, d.month


def _redirect_sales(request):
    """Return to Sales on the same site (/home vs /mgmt) the request came from."""
    ns = getattr(request, "ns_site_namespace", None) or "Dashboard"
    return redirect(f"{ns}:sales")


# Product names for product detail pages (product 1-4)
PRODUCTS = {
    1: "Rust Protection",
    2: "Extended Warranty",
    3: "Paint Protection",
    4: "Fabric Guard",
}


def home(request):
    """Home page (linked from logo only, not in nav)."""
    return render(request, "Dashboard/home.html")


def index(request):
    """The Dashboard for C3."""
    sales_products = list(SalesProduct.objects.all())

    y, m = _sales_month_today()
    can_view_all = user_can_view_all_dealerships(request.user)
    home_dealership = getattr(request, "ns_dealership", None)
    if not can_view_all and not home_dealership:
        return HttpResponseForbidden("No dealership is assigned to your user.")

    dealership_count = Dealership.objects.count() if can_view_all else 1

    daily_sales_scope = DailySale.objects.filter(date__year=y, date__month=m)
    if not can_view_all and home_dealership:
        daily_sales_scope = daily_sales_scope.filter(dealership=home_dealership)

    sales_by_product_id = {
        row["product_id"]: (row["total"] or 0)
        for row in daily_sales_scope
        .values("product_id")
        .annotate(total=Sum("amount"))
    }

    dashboard_rows = []
    revenue_goal = Decimal("0")
    revenue_achieved = Decimal("0")

    for p in sales_products:
        sales_this_month = int(sales_by_product_id.get(p.id, 0) or 0)
        goal_units = int(p.goal or 0) * int(dealership_count or 1)
        goal_pct = round((sales_this_month / goal_units) * 100) if goal_units else None

        dashboard_rows.append(
            {
                "product": p,
                "sales_this_month": sales_this_month,
                "goal_pct": goal_pct,
            }
        )

        # Revenue progress uses the current scope:
        # - dealership portal: goal is per-dealership
        # - management portal: goal is company-wide (sum of dealership goals)
        # Do NOT cap achieved revenue at the unit goal; if you exceed goal, % should exceed 100%.
        price = p.price or Decimal("0")
        revenue_goal += Decimal(int(p.goal or 0) * int(dealership_count or 1)) * price
        revenue_achieved += Decimal(sales_this_month) * price

    if revenue_goal > 0:
        revenue_goal_pct_raw = (revenue_achieved / revenue_goal) * Decimal("100")
    else:
        revenue_goal_pct_raw = Decimal("0")

    # Clamp only for the circular chart fill (but keep raw % for display).
    revenue_goal_pct = revenue_goal_pct_raw
    if revenue_goal_pct < 0:
        revenue_goal_pct = Decimal("0")
    if revenue_goal_pct > 100:
        revenue_goal_pct = Decimal("100")

    # Inventory bar chart (x=products, y=units, grouped by dealership).
    inventory_totals_png_b64 = None
    try:
        physical_products = list(
            SalesProduct.objects.filter(tracks_inventory=True).order_by("display_order", "id")
        )
        if can_view_all:
            dealerships = list(Dealership.objects.order_by("name"))
        else:
            dealerships = [home_dealership] if home_dealership else []

        if physical_products and dealerships:
            import base64
            from io import BytesIO

            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import numpy as np

            product_labels = [p.name for p in physical_products]
            x = np.arange(len(product_labels))
            width = 0.8 / max(1, len(dealerships))

            # Larger chart so it is readable on the dashboard.
            fig, ax = plt.subplots(figsize=(24, 11))
            for i, deal in enumerate(dealerships):
                quantities = [quantity_on_hand(p, deal) for p in physical_products]
                offset = (i - (len(dealerships) - 1) / 2) * width
                ax.bar(
                    x + offset,
                    quantities,
                    width=width,
                    label=deal.name,
                    color=deal.chart_color_hex(),
                    edgecolor="white",
                    linewidth=0.6,
                )

            ax.set_title("Inventory by product (per dealership)", fontsize=18, fontweight="bold")
            ax.set_ylabel("Units", fontsize=14, fontweight="bold")
            ax.set_xticks(x)
            ax.set_xticklabels(
                product_labels,
                rotation=45,
                ha="right",
                fontsize=13,
            )
            ax.tick_params(axis="x", labelsize=13)
            ax.tick_params(axis="y", labelsize=13)
            for t in ax.get_xticklabels():
                t.set_fontweight("bold")
            for t in ax.get_yticklabels():
                t.set_fontweight("bold")
            ax.grid(axis="y", linestyle="--", alpha=0.25)
            # Make legend much larger for readability.
            ax.legend(fontsize=18, ncol=2, prop={"weight": "bold"})
            fig.tight_layout(pad=1.5)

            buf = BytesIO()
            fig.savefig(buf, format="png", dpi=240)
            inventory_totals_png_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            plt.close(fig)
    except Exception:
        inventory_totals_png_b64 = None

    context = {
        "dashboard_rows": dashboard_rows,
        "revenue_goal_pct": float(revenue_goal_pct),
        "revenue_goal_pct_raw": float(revenue_goal_pct_raw),
        "revenue_goal": f"{revenue_goal.quantize(Decimal('0.01'))}",
        "revenue_achieved": f"{revenue_achieved.quantize(Decimal('0.01'))}",
        "inventory_totals_png_b64": inventory_totals_png_b64,
        "revenue_scope_label": "Company Wide" if can_view_all else (home_dealership.name if home_dealership else "Dealership"),
    }
    return render(request, "Dashboard/index.html", context)


def product(request, product_id):
    """Product detail page (product 1-4)."""
    if product_id not in PRODUCTS:
        from django.http import Http404
        raise Http404("Product not found")
    context = {"product_id": product_id, "product_name": PRODUCTS[product_id]}
    return render(request, "Dashboard/product.html", context)


def sales(request):
    """Sales tab with editable C3 Product Performance table (sales this month)."""
    products = SalesProduct.objects.all()
    y, m = _sales_month_today()
    can_view_all = user_can_view_all_dealerships(request.user)
    home_dealership = getattr(request, "ns_dealership", None)
    if not can_view_all and not home_dealership:
        return HttpResponseForbidden("No dealership is assigned to your user.")

    dealership_count = Dealership.objects.count() if can_view_all else 1

    daily_sales_qs = DailySale.objects.filter(
        date__year=y,
        date__month=m,
    ).select_related("product", "dealership", "entered_by").order_by("-date", "-id")

    if not can_view_all and home_dealership:
        daily_sales_qs = daily_sales_qs.filter(dealership=home_dealership)

    sales_totals = {
        row["product_id"]: int(row["total"] or 0)
        for row in daily_sales_qs.values("product_id").annotate(total=Sum("amount"))
    }

    product_rows = []
    for p in products:
        sales_this_month = int(sales_totals.get(p.id, 0) or 0)
        goal_units = int(p.goal or 0) * int(dealership_count or 1)
        goal_pct = round((sales_this_month / goal_units) * 100) if goal_units else None
        product_rows.append(
            {
                "product": p,
                "sales_this_month": sales_this_month,
                "goal_pct": goal_pct,
            }
        )

    context = {
        "product_rows": product_rows,
        "daily_sales_this_month": daily_sales_qs,
        "add_form": SalesProductForm(),
        "add_daily_form": DailySaleForm(user=request.user),
        "show_management_sales_archive": False,
    }

    if _can_view_management_sales_archive(request.user):
        hist_dealership = (request.GET.get("hist_dealership") or "").strip()
        hist_product = (request.GET.get("hist_product") or "").strip()
        hist_seller = (request.GET.get("hist_seller") or "").strip()
        hist_q = (request.GET.get("hist_q") or "").strip()

        history_qs = DailySale.objects.select_related(
            "product", "dealership", "entered_by"
        ).order_by("-date", "-id")

        if hist_dealership.isdigit():
            history_qs = history_qs.filter(dealership_id=int(hist_dealership))
        if hist_product.isdigit():
            history_qs = history_qs.filter(product_id=int(hist_product))
        if hist_seller == "__none__":
            history_qs = history_qs.filter(entered_by__isnull=True)
        elif hist_seller.isdigit():
            history_qs = history_qs.filter(entered_by_id=int(hist_seller))

        if hist_q:
            q_norm = hist_q.lstrip("#").strip()
            q_filter = Q(order_number__icontains=hist_q)
            if q_norm != hist_q:
                q_filter |= Q(order_number__icontains=q_norm)
            if hist_q.isdigit():
                q_filter |= Q(pk=int(hist_q))
            history_qs = history_qs.filter(q_filter)

        paginator = Paginator(history_qs, MANAGEMENT_SALES_HISTORY_PER_PAGE)
        hist_page = request.GET.get("hist_page") or "1"
        try:
            page_obj = paginator.page(hist_page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages or 1)

        seller_ids = (
            DailySale.objects.exclude(entered_by_id__isnull=True)
            .values_list("entered_by_id", flat=True)
            .distinct()
        )
        User = get_user_model()
        sellers_for_history = User.objects.filter(pk__in=seller_ids).order_by(
            "first_name", "last_name", "username"
        )

        preserve_pairs = []
        for key in request.GET:
            if key == "hist_page":
                continue
            if key.startswith("hist_"):
                for val in request.GET.getlist(key):
                    preserve_pairs.append((key, val))
        management_history_preserve_qs = urlencode(preserve_pairs)

        context.update(
            {
                "show_management_sales_archive": True,
                "management_history_page": page_obj,
                "management_history_filters": {
                    "dealership": hist_dealership,
                    "product": hist_product,
                    "seller": hist_seller,
                    "q": hist_q,
                },
                "management_history_preserve_qs": management_history_preserve_qs,
                "dealerships_for_history": Dealership.objects.order_by("name"),
                "products_for_history": SalesProduct.objects.order_by(
                    "display_order", "id"
                ),
                "sellers_for_history": sellers_for_history,
            }
        )

    return render(request, "Dashboard/sales.html", context)


@require_POST
def sales_add_product(request):
    """Add a new product row to the sales table."""
    form = SalesProductForm(request.POST)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.display_order = SalesProduct.objects.count()
        obj.save()
    else:
        _messages_for_invalid_form(request, form, context_note="Product was not added:")
    return _redirect_sales(request)


def _messages_for_invalid_form(request, form, *, context_note=None):
    """Flash each validation error; always emit at least one message when the form is invalid."""
    prefix = f"{context_note} " if context_note else ""
    added = False
    for msg in form.non_field_errors():
        messages.error(request, f"{prefix}{msg}")
        added = True
    for field_name, errs in form.errors.items():
        if field_name == "__all__":
            continue
        fld = form.fields.get(field_name)
        label = fld.label if fld else field_name.replace("_", " ").title()
        for err in errs:
            messages.error(request, f"{prefix}{label}: {err}")
            added = True
    if not added:
        messages.error(
            request,
            f"{prefix}This was not saved. Please check all fields and try again."
            if prefix
            else "This was not saved. Please check all fields and try again.",
        )


@require_POST
def sales_add_daily(request):
    """Add a sale. Allowed only for admin, Sales Rep, Dealership User."""
    if not _can_modify_daily_sales(request.user):
        messages.error(request, "Sale was not added: you don't have permission to add sales.")
        return _redirect_sales(request)
    form = DailySaleForm(request.POST, user=request.user)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.entered_by = request.user
        obj.save()
        apply_sale_delta(obj.product, obj.dealership, int(obj.amount))
    else:
        _messages_for_invalid_form(request, form, context_note="Sale was not added:")
    return _redirect_sales(request)


def sales_edit_daily(request, daily_pk):
    """Edit a sale. Allowed only for admin, Sales Rep, Dealership User."""
    if not _can_modify_daily_sales(request.user):
        messages.error(request, "Sale was not updated: you don't have permission to edit sales.")
        return _redirect_sales(request)
    obj = get_object_or_404(DailySale, pk=daily_pk)
    if request.method == "POST":
        old_product = obj.product
        old_dealership = obj.dealership
        old_amount = int(obj.amount)
        form = DailySaleForm(request.POST, instance=obj, user=request.user)
        if form.is_valid():
            saved = form.save()
            if old_product.pk != saved.product.pk or old_dealership.pk != saved.dealership.pk:
                # Remove old delta, apply new delta.
                apply_sale_delta(old_product, old_dealership, -old_amount)
                apply_sale_delta(saved.product, saved.dealership, int(saved.amount))
            else:
                apply_sale_delta(
                    saved.product,
                    saved.dealership,
                    int(saved.amount) - old_amount,
                )
            return _redirect_sales(request)
        _messages_for_invalid_form(request, form, context_note="Sale was not updated:")
    else:
        form = DailySaleForm(instance=obj, user=request.user)
    context = {"form": form, "daily_sale": obj}
    return render(request, "Dashboard/sales_edit_daily.html", context)


@require_POST
def sales_delete_daily(request, daily_pk):
    """Delete a sale. Allowed only for admin, Sales Rep, Dealership User."""
    if not _can_modify_daily_sales(request.user):
        messages.error(request, "Sale was not deleted: you don't have permission.")
        return _redirect_sales(request)
    obj = get_object_or_404(DailySale, pk=daily_pk)
    apply_sale_delta(obj.product, obj.dealership, -int(obj.amount))
    obj.delete()
    return _redirect_sales(request)


@require_POST
def sales_delete_product(request, product_pk):
    """Remove a product row from the sales table."""
    obj = get_object_or_404(SalesProduct, pk=product_pk)
    obj.delete()
    return _redirect_sales(request)


@require_POST
def sales_update_product(request, product_pk):
    """Update goal and price for a sales product."""
    obj = get_object_or_404(SalesProduct, pk=product_pk)
    try:
        goal = int(request.POST.get("goal", 1) or 1)
    except (TypeError, ValueError):
        messages.error(
            request,
            f'Product "{obj.name}": goal was not updated; enter a whole number. Other fields were not changed.',
        )
        return _redirect_sales(request)
    obj.goal = max(1, goal)
    try:
        price = Decimal(str(request.POST.get("price", 0) or 0))
        if price < 0:
            price = Decimal("0")
        obj.price = price
    except (InvalidOperation, ValueError, TypeError):
        messages.error(
            request,
            f'Product "{obj.name}": price was not updated; enter a valid number. Goal was still saved.',
        )
    obj.save()
    return _redirect_sales(request)


def _can_view_all_inventory(user):
    """Managers/admin: see inventory for every dealership."""
    if not user.is_authenticated:
        return False
    if _staff_or_superuser(user):
        return True
    return user.groups.filter(name="Management").exists()


def _can_submit_inventory_order(user):
    """Sales Rep and Dealership User can submit stock requests."""
    if not user.is_authenticated:
        return False
    if _staff_or_superuser(user):
        return True
    return user.groups.filter(name__in=["Sales Rep", "Dealership User"]).exists()


def _can_manage_inventory_orders(user):
    """Deliver, cancel, or adjust stock for orders (Management, Back Office, Sales Rep, Dealership User)."""
    if not user.is_authenticated:
        return False
    if _staff_or_superuser(user):
        return True
    return user.groups.filter(
        name__in=["Management", "Back Office", "Sales Rep", "Dealership User"]
    ).exists()


def _inventory_order_scope_denied_response(request, order):
    """Sales Rep / Dealership User may only act on orders for their home dealership."""
    if _staff_or_superuser(request.user) or request.user.groups.filter(
        name__in=["Management", "Back Office"]
    ).exists():
        return None
    if request.user.groups.filter(name__in=["Sales Rep", "Dealership User"]).exists():
        home = user_home_dealership(request.user)
        if not home or order.dealership_id != home.pk:
            return HttpResponseForbidden(
                "You can only manage inventory orders for your home dealership."
            )
    return None


def inventory(request):
    """
    Inventory page: per-dealership stock table + inventory request/order tracking.
    """
    if not request.user.is_authenticated:
        return HttpResponseForbidden("You must be logged in.")

    can_view_all = _can_view_all_inventory(request.user)
    can_submit = _can_submit_inventory_order(request.user)
    can_manage_orders = _can_manage_inventory_orders(request.user)

    physical_products = (
        SalesProduct.objects.filter(tracks_inventory=True)
        .order_by("display_order", "id")
        .all()
    )

    home = user_home_dealership(request.user) if not can_view_all else None
    if can_view_all:
        dealerships = list(Dealership.objects.order_by("name"))
    else:
        # If a user has no assigned home dealership yet, show everything as a WIP fallback
        # so the page remains usable.
        dealerships = [home] if home else list(Dealership.objects.order_by("name"))

    dealership_sections = []
    for deal in dealerships:
        rows = []
        for p in physical_products:
            qty = quantity_on_hand(p, deal)
            _, status_label, badge_variant = inventory_status_tuple(qty)
            rows.append(
                {
                    "product": p,
                    "quantity": qty,
                    "status_label": status_label,
                    "badge_variant": badge_variant,
                }
            )
        dealership_sections.append(
            {
                "dealership": deal,
                "rows": rows,
                "accent_color": deal.chart_color_hex(),
            }
        )

    orders_qs = InventoryOrder.objects.select_related(
        "product",
        "dealership",
        "requested_by",
        "delivered_by",
        "cancelled_by",
    ).order_by("-date_requested")
    if not can_view_all and home:
        orders_qs = orders_qs.filter(dealership=home)

    order_form = InventoryRequestForm(user=request.user)
    pending_order_count = orders_qs.filter(status=InventoryOrder.STATUS_PENDING).count()

    context = {
        "dealership_sections": dealership_sections,
        "physical_products": physical_products,
        "inventory_orders": orders_qs[:200],
        "order_form": order_form,
        "can_view_all_inventory": can_view_all,
        "can_submit_inventory_order": can_submit,
        "can_manage_inventory_orders": can_manage_orders,
        "user_dealership": user_home_dealership(request.user),
        "pending_order_count": pending_order_count,
    }
    return render(request, "Dashboard/inventory.html", context)


@require_POST
def inventory_order_submit(request):
    """Create a pending InventoryOrder."""
    if not _can_submit_inventory_order(request.user):
        return HttpResponseForbidden("You don't have permission to submit inventory orders.")
    form = InventoryRequestForm(request.POST, user=request.user)
    if form.is_valid():
        order = form.save(commit=False)
        order.requested_by = request.user
        order.status = InventoryOrder.STATUS_PENDING
        order.save()
        messages.success(
            request,
            f"Inventory request submitted successfully (order #{order.display_order_id}). Status: Pending.",
        )
    else:
        messages.error(request, f"Could not submit order. {form.errors.as_text()}")
    return redirect("Dashboard:inventory")


@require_POST
def inventory_order_deliver(request, order_pk):
    """Mark order delivered and add quantity to on-hand inventory. Sales Rep / Dealership User only for their dealership."""
    if not _can_manage_inventory_orders(request.user):
        return HttpResponseForbidden("You don't have permission to mark orders as delivered.")

    order = get_object_or_404(InventoryOrder, pk=order_pk)

    denied = _inventory_order_scope_denied_response(request, order)
    if denied:
        return denied

    if order.status != InventoryOrder.STATUS_PENDING:
        messages.warning(request, "That order is not pending.")
        return redirect("Dashboard:inventory")

    fulfill_inventory_order(order, request.user)
    messages.success(
        request,
        f"Order #{order.display_order_id} marked delivered. Stock at {order.dealership.name} updated.",
    )
    return redirect("Dashboard:inventory")


@require_POST
def inventory_order_cancel(request, order_pk):
    """Cancel a pending order (no stock change). Same role rules as deliver."""
    if not _can_manage_inventory_orders(request.user):
        return HttpResponseForbidden("You don't have permission to cancel inventory orders.")

    order = get_object_or_404(InventoryOrder, pk=order_pk)

    denied = _inventory_order_scope_denied_response(request, order)
    if denied:
        return denied

    if order.status != InventoryOrder.STATUS_PENDING:
        messages.warning(request, "That order is not pending.")
        return redirect("Dashboard:inventory")

    cancel_inventory_order(order, request.user)
    messages.success(
        request,
        f"Order #{order.display_order_id} cancelled.",
    )
    return redirect("Dashboard:inventory")


def _can_access_claims(user):
    """WIP Claims page access."""
    if not user.is_authenticated:
        return False
    if _staff_or_superuser(user):
        return True
    return user.groups.filter(
        name__in=["Management", "Back Office", "Sales Rep", "Dealership User"]
    ).exists()


def _can_change_claim_status(user):
    """Approve/reject/etc. in the portal: staff, superuser, Management, or Back Office."""
    if not user.is_authenticated:
        return False
    if _staff_or_superuser(user):
        return True
    return user.groups.filter(name__in=["Management", "Back Office"]).exists()


def _can_access_inspections(user):
    """WIP Inspections page access (same roles as claims for now)."""
    return _can_access_claims(user)


def claims(request):
    """Claims: list (scoped by dealership) and submit new claims."""
    if not _can_access_claims(request.user):
        return HttpResponseForbidden("You don't have permission to view claims.")

    can_view_all = user_can_view_all_dealerships(request.user)
    home_dealership = getattr(request, "ns_dealership", None)
    if not can_view_all and not home_dealership:
        return HttpResponseForbidden("No dealership is assigned to your user.")

    ns = getattr(request, "ns_site_namespace", None) or "Dashboard"

    if request.method == "POST":
        form = ClaimForm(request.POST, user=request.user)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.submitted_by = request.user
            obj.status = Claim.STATUS_PENDING
            obj.save()
            messages.success(
                request,
                f"Claim #{obj.pk} submitted successfully. Status: Pending.",
            )
            return redirect(f"{ns}:claims")
        _messages_for_invalid_form(request, form, context_note="Claim was not submitted:")
    else:
        form = ClaimForm(user=request.user)

    claims_qs = Claim.objects.select_related(
        "daily_sale",
        "daily_sale__dealership",
        "daily_sale__product",
        "submitted_by",
    ).order_by("-date_submitted", "-id")
    if not can_view_all and home_dealership:
        claims_qs = claims_qs.filter(daily_sale__dealership=home_dealership)

    context = {
        "claim_form": form,
        "claims_list": claims_qs[:500],
        "claims_scope_label": (
            "Company wide" if can_view_all else (home_dealership.name if home_dealership else "Dealership")
        ),
        "can_change_claim_status": _can_change_claim_status(request.user),
    }
    return render(request, "Dashboard/claims.html", context)


def claim_detail(request, claim_pk):
    """Single claim: full fields including notes (same access scope as claims list)."""
    if not _can_access_claims(request.user):
        return HttpResponseForbidden("You don't have permission to view claims.")

    can_view_all = user_can_view_all_dealerships(request.user)
    home_dealership = getattr(request, "ns_dealership", None)
    if not can_view_all and not home_dealership:
        return HttpResponseForbidden("No dealership is assigned to your user.")

    qs = Claim.objects.select_related(
        "daily_sale",
        "daily_sale__dealership",
        "daily_sale__product",
        "submitted_by",
    )
    if not can_view_all and home_dealership:
        qs = qs.filter(daily_sale__dealership=home_dealership)
    claim = get_object_or_404(qs, pk=claim_pk)

    status_form = None
    if _can_change_claim_status(request.user):
        status_form = ClaimStatusForm(initial={"status": claim.status})

    return render(
        request,
        "Dashboard/claim_detail.html",
        {
            "claim": claim,
            "can_change_claim_status": _can_change_claim_status(request.user),
            "claim_status_form": status_form,
        },
    )


@require_POST
def claim_set_status(request, claim_pk):
    """Update claim status (staff, Management, or Back Office only)."""
    if not _can_change_claim_status(request.user):
        return HttpResponseForbidden("You don't have permission to change claim status.")

    can_view_all = user_can_view_all_dealerships(request.user)
    home_dealership = getattr(request, "ns_dealership", None)
    if not can_view_all and not home_dealership:
        return HttpResponseForbidden("No dealership is assigned to your user.")

    qs = Claim.objects.select_related(
        "daily_sale",
        "daily_sale__dealership",
        "daily_sale__product",
        "submitted_by",
    )
    if not can_view_all and home_dealership:
        qs = qs.filter(daily_sale__dealership=home_dealership)
    claim = get_object_or_404(qs, pk=claim_pk)

    form = ClaimStatusForm(request.POST)
    ns = getattr(request, "ns_site_namespace", None) or "Dashboard"
    if form.is_valid():
        claim.status = form.cleaned_data["status"]
        claim.save(update_fields=["status"])
        messages.success(
            request,
            f"Claim #{claim.pk} status updated to {claim.get_status_display()}.",
        )
    else:
        _messages_for_invalid_form(request, form, context_note="Status was not updated:")

    return redirect(f"{ns}:claim_detail", claim_pk=claim.pk)


def inspections(request):
    """Vehicle inspections: list (scoped by dealership), optional VIN filter, record new inspection."""
    if not _can_access_inspections(request.user):
        return HttpResponseForbidden("You don't have permission to view inspections.")

    can_view_all = user_can_view_all_dealerships(request.user)
    home_dealership = getattr(request, "ns_dealership", None)
    if not can_view_all and not home_dealership:
        return HttpResponseForbidden("No dealership is assigned to your user.")

    ns = getattr(request, "ns_site_namespace", None) or "Dashboard"

    inspections_qs = Inspection.objects.select_related(
        "daily_sale",
        "dealership",
        "product",
        "recorded_by",
    )
    if not can_view_all and home_dealership:
        inspections_qs = inspections_qs.filter(dealership=home_dealership)

    vin_filter = (request.GET.get("vin") or "").strip().upper()
    if vin_filter:
        inspections_qs = inspections_qs.filter(vin__icontains=vin_filter)

    if request.method == "POST":
        form = InspectionForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.recorded_by = request.user
            obj.save()
            for f in request.FILES.getlist("photos"):
                if not f:
                    continue
                InspectionPhoto.objects.create(inspection=obj, image=f)
            messages.success(
                request,
                f"Inspection #{obj.pk} recorded for VIN {obj.vin} ({'Pass' if obj.passed else 'Fail'}).",
            )
            return redirect(f"{ns}:inspections")
        _messages_for_invalid_form(request, form, context_note="Inspection was not saved:")
    else:
        form = InspectionForm(user=request.user)

    context = {
        "inspection_form": form,
        "inspections_list": inspections_qs.order_by("-inspection_date", "-id")[:500],
        "inspections_scope_label": (
            "Company wide" if can_view_all else (home_dealership.name if home_dealership else "Dealership")
        ),
        "vin_filter": vin_filter,
    }
    return render(request, "Dashboard/inspections.html", context)


def inspection_detail(request, inspection_pk):
    """Single inspection: full fields (same dealership scope as inspections list)."""
    if not _can_access_inspections(request.user):
        return HttpResponseForbidden("You don't have permission to view inspections.")

    can_view_all = user_can_view_all_dealerships(request.user)
    home_dealership = getattr(request, "ns_dealership", None)
    if not can_view_all and not home_dealership:
        return HttpResponseForbidden("No dealership is assigned to your user.")

    qs = Inspection.objects.select_related(
        "daily_sale",
        "dealership",
        "product",
        "recorded_by",
    ).prefetch_related("photos")
    if not can_view_all and home_dealership:
        qs = qs.filter(dealership=home_dealership)
    inspection = get_object_or_404(qs, pk=inspection_pk)

    return render(
        request,
        "Dashboard/inspection_detail.html",
        {"inspection": inspection},
    )


def Reports(request):
    """Show all Reports."""
    reportlist = Report.objects.order_by("date_added")
    context = {"Reports": reportlist}
    return render(request, "Dashboard/Reports.html", context)


def report(request, report_id):
    """Show a single Report and its entries."""
    myreport = Report.objects.get(id=report_id)
    myentries = myreport.entry_set.order_by('-date_added').prefetch_related("documents")
    context = {'report': myreport, 'entries': myentries, 'can_delete_reports': _is_management(request.user)}
    return render(request, 'Dashboard/report.html', context)


def new_report(request):
    """Add a new Report."""
    if request.method != 'POST':
        # No data submitted; create a blank form.
        form = ReportForm()
    else:
        # POST data submitted; process data.
        form = ReportForm(data=request.POST)
        if form.is_valid():
            form.save()
            return redirect('Dashboard:Reports')

    # Display a blank or invalid form.
    context = {'form': form}
    return render(request, 'Dashboard/new_report.html', context)
    
def new_entry(request, report_id):
    """Add a new entry for a particular report."""
    report = Report.objects.get(id=report_id)
    
    if request.method != 'POST':
        # No data submitted; create a blank form.
        form = EntryForm()
    else:
        # POST data submitted; process data.
        form = EntryForm(data=request.POST)
        if form.is_valid():
            new_entry = form.save(commit=False)
            new_entry.Report = report
            new_entry.save()
            for f in request.FILES.getlist("documents"):
                name = (getattr(f, "name", "") or "").lower()
                ctype = (getattr(f, "content_type", "") or "").lower()
                if name.endswith(".pdf") or ctype == "application/pdf":
                    EntryDocument.objects.create(entry=new_entry, file=f)
            return redirect('Dashboard:report', report_id=report_id)
               
    # Display a blank or invalid form.
    context = {'report': report, 'form': form}
    return render(request, 'Dashboard/new_entry.html', context)


def edit_entry(request, entry_id):
    """Edit an existing entry."""
    entry = get_object_or_404(Entry, id=entry_id)
    report = entry.Report

    if request.method != "POST":
        form = EntryForm(instance=entry)
    else:
        form = EntryForm(instance=entry, data=request.POST)
        if form.is_valid():
            form.save()
            for f in request.FILES.getlist("documents"):
                name = (getattr(f, "name", "") or "").lower()
                ctype = (getattr(f, "content_type", "") or "").lower()
                if name.endswith(".pdf") or ctype == "application/pdf":
                    EntryDocument.objects.create(entry=entry, file=f)
            return redirect("Dashboard:report", report_id=report.id)

    context = {"entry": entry, "report": report, "form": form, "can_delete_reports": _is_management(request.user)}
    return render(request, "Dashboard/edit_entry.html", context)


@require_POST
def delete_entry_document(request, doc_id):
    """Delete a PDF document attached to an entry."""
    if not _is_management(request.user):
        return HttpResponseForbidden("You don't have permission to delete PDFs.")
    doc = get_object_or_404(EntryDocument, id=doc_id)
    report_id = doc.entry.Report_id
    doc.file.delete(save=False)
    doc.delete()
    return redirect("Dashboard:report", report_id=report_id)


@xframe_options_sameorigin
def entry_document_inline(request, doc_id):
    """Serve an entry PDF inline (for embedding)."""
    doc = get_object_or_404(EntryDocument, id=doc_id)
    # FileResponse sets Content-Type; we also force inline disposition.
    resp = FileResponse(doc.file.open("rb"), content_type="application/pdf")
    filename = doc.file.name.rsplit("/", 1)[-1]
    resp["Content-Disposition"] = f'inline; filename="{filename}"'
    return resp


@require_POST
def delete_entry(request, entry_id):
    """Delete an entry and any attached PDFs."""
    if not _is_management(request.user):
        return HttpResponseForbidden("You don't have permission to delete entries.")
    entry = get_object_or_404(Entry, id=entry_id)
    report_id = entry.Report_id
    # Delete files from storage first
    for doc in entry.documents.all():
        doc.file.delete(save=False)
    entry.delete()
    return redirect("Dashboard:report", report_id=report_id)


@require_POST
def delete_report(request, report_id):
    """Delete a report and all entries/PDFs (Management only)."""
    if not _is_management(request.user):
        return HttpResponseForbidden("You don't have permission to delete reports.")
    report = get_object_or_404(Report, id=report_id)
    # Delete PDFs from storage first
    for entry in report.entry_set.all().prefetch_related("documents"):
        for doc in entry.documents.all():
            doc.file.delete(save=False)
    report.delete()
    return redirect("Dashboard:Reports")