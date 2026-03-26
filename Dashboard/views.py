from decimal import Decimal, InvalidOperation

from django.db.models import Sum
from django.contrib import messages
from django.http import FileResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST
from .forms import ReportForm, EntryForm, SalesProductForm, DailySaleForm
from .forms import InventoryRequestForm
from .inventory_services import (
    apply_sale_delta,
    fulfill_inventory_order,
    get_or_create_inventory_row,
    quantity_on_hand,
    inventory_status_tuple,
    user_home_dealership,
)
from .models import (
    Dealership,
    DailySale,
    Entry,
    EntryDocument,
    InventoryOrder,
    ProductInventory,
    Report,
    SalesProduct,
)


def _can_modify_daily_sales(user):
    """True if user is staff, Sales Rep, or Dealership User."""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    group_names = set(user.groups.values_list("name", flat=True))
    return "Sales Rep" in group_names or "Dealership User" in group_names


def _is_management(user):
    """True if user is in the Management group."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name="Management").exists()


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

    now = timezone.now()
    sales_by_product_id = {
        row["product_id"]: (row["total"] or 0)
        for row in DailySale.objects.filter(date__year=now.year, date__month=now.month)
        .values("product_id")
        .annotate(total=Sum("amount"))
    }

    dashboard_rows = []
    revenue_goal = Decimal("0")
    revenue_achieved = Decimal("0")

    for p in sales_products:
        sales_this_month = int(sales_by_product_id.get(p.id, 0) or 0)
        goal_pct = round((sales_this_month / p.goal) * 100) if p.goal else None

        dashboard_rows.append(
            {
                "product": p,
                "sales_this_month": sales_this_month,
                "goal_pct": goal_pct,
            }
        )

        # Revenue progress is company-wide actual revenue vs revenue goal.
        # Do NOT cap achieved revenue at the unit goal; if you exceed goal, % should exceed 100%.
        price = p.price or Decimal("0")
        revenue_goal += Decimal(p.goal) * price
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
        dealerships = list(Dealership.objects.order_by("name"))

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
                ax.bar(x + offset, quantities, width=width, label=deal.name)

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
    now = timezone.now()
    daily_sales_this_month = DailySale.objects.filter(
        date__year=now.year,
        date__month=now.month,
    ).select_related("product", "dealership").order_by("-date", "-id")
    context = {
        "sales_products": products,
        "daily_sales_this_month": daily_sales_this_month,
        "add_form": SalesProductForm(),
        "add_daily_form": DailySaleForm(user=request.user),
    }
    return render(request, "Dashboard/sales.html", context)


@require_POST
def sales_add_product(request):
    """Add a new product row to the sales table."""
    form = SalesProductForm(request.POST)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.display_order = SalesProduct.objects.count()
        obj.save()
    return redirect("Dashboard:sales")


@require_POST
def sales_add_daily(request):
    """Add a daily sale. Allowed only for admin, Sales Rep, Dealership User."""
    if not _can_modify_daily_sales(request.user):
        return HttpResponseForbidden("You don't have permission to add daily sales.")
    form = DailySaleForm(request.POST, user=request.user)
    if form.is_valid():
        obj = form.save()
        apply_sale_delta(obj.product, obj.dealership, int(obj.amount))
    return redirect("Dashboard:sales")


def sales_edit_daily(request, daily_pk):
    """Edit a daily sale. Allowed only for admin, Sales Rep, Dealership User."""
    if not _can_modify_daily_sales(request.user):
        return HttpResponseForbidden("You don't have permission to edit daily sales.")
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
            return redirect("Dashboard:sales")
    else:
        form = DailySaleForm(instance=obj, user=request.user)
    context = {"form": form, "daily_sale": obj}
    return render(request, "Dashboard/sales_edit_daily.html", context)


@require_POST
def sales_delete_daily(request, daily_pk):
    """Delete a daily sale. Allowed only for admin, Sales Rep, Dealership User."""
    if not _can_modify_daily_sales(request.user):
        return HttpResponseForbidden("You don't have permission to delete daily sales.")
    obj = get_object_or_404(DailySale, pk=daily_pk)
    apply_sale_delta(obj.product, obj.dealership, -int(obj.amount))
    obj.delete()
    return redirect("Dashboard:sales")


@require_POST
def sales_delete_product(request, product_pk):
    """Remove a product row from the sales table."""
    obj = get_object_or_404(SalesProduct, pk=product_pk)
    obj.delete()
    return redirect("Dashboard:sales")


@require_POST
def sales_update_product(request, product_pk):
    """Update goal and price for a sales product."""
    obj = get_object_or_404(SalesProduct, pk=product_pk)
    goal = int(request.POST.get("goal", 1) or 1)
    obj.goal = max(1, goal)
    try:
        price = Decimal(str(request.POST.get("price", 0) or 0))
        if price < 0:
            price = Decimal("0")
        obj.price = price
    except (InvalidOperation, ValueError, TypeError):
        pass
    obj.save()
    return redirect("Dashboard:sales")


def _can_view_all_inventory(user):
    """Managers/admin: see inventory for every dealership."""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return user.groups.filter(name="Management").exists()


def _can_submit_inventory_order(user):
    """Sales Rep and Dealership User can submit stock requests."""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return user.groups.filter(name__in=["Sales Rep", "Dealership User"]).exists()


def _can_manage_inventory_orders(user):
    """Mark requests as delivered and increase on-hand counts."""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return user.groups.filter(name__in=["Management", "Back Office"]).exists()


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
        dealership_sections.append({"dealership": deal, "rows": rows})

    orders_qs = InventoryOrder.objects.select_related("product", "dealership", "requested_by").order_by(
        "-date_requested"
    )
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
    """Manager/admin: mark order delivered and add quantity to on-hand inventory."""
    if not _can_manage_inventory_orders(request.user):
        return HttpResponseForbidden("You don't have permission to mark orders as delivered.")

    order = get_object_or_404(InventoryOrder, pk=order_pk)
    if order.status != InventoryOrder.STATUS_PENDING:
        messages.warning(request, "That order is not pending.")
        return redirect("Dashboard:inventory")

    fulfill_inventory_order(order)
    messages.success(
        request,
        f"Order #{order.display_order_id} marked delivered. Stock at {order.dealership.name} updated.",
    )
    return redirect("Dashboard:inventory")


def _can_access_claims(user):
    """WIP Claims page access."""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return user.groups.filter(
        name__in=["Management", "Back Office", "Sales Rep", "Dealership User"]
    ).exists()


def _can_access_inspections(user):
    """WIP Inspections page access (same roles as claims for now)."""
    return _can_access_claims(user)


def claims(request):
    """Claims page (WIP stub)."""
    if not _can_access_claims(request.user):
        return HttpResponseForbidden("You don't have permission to view claims.")

    wip_mode = True
    claim_status_choices = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("received", "Received"),
    ]

    # Dummy context (test stub) to keep the page usable until real models exist.
    dealerships = [
        {"pk": 1, "name": "Default Dealership"},
        {"pk": 2, "name": "Northside Motors"},
        {"pk": 3, "name": "Westside Auto"},
    ]
    products = list(SalesProduct.objects.all()[:6])
    products_stub = [{"pk": p.pk, "name": p.name} for p in products]

    sample_claims = [
        {
            "id": 1,
            "status": "pending",
            "dealership": dealerships[0],
            "product": products_stub[0] if products_stub else {"pk": None, "name": "—"},
            "quantity": 4,
            "submitted_at": timezone.now(),
            "customer_name": "Customer 1",
        }
    ]

    submitted_stub_data = None
    if request.method == "POST":
        submitted_stub_data = {
            "customer_name": (request.POST.get("customer_name") or "").strip(),
            "dealership_id": request.POST.get("dealership_id") or "",
            "product_id": request.POST.get("product_id") or "",
            "order_number": (request.POST.get("order_number") or "").strip(),
            "quantity": request.POST.get("quantity") or "",
            "reason": (request.POST.get("reason") or "").strip(),
        }
        messages.success(request, "Claim submission received (WIP stub). No data was saved yet.")

    context = {
        "wip_mode": wip_mode,
        "claim_status_choices": claim_status_choices,
        "dealerships": dealerships,
        "products": products_stub,
        "sample_claims": sample_claims,
        "submitted_stub_data": submitted_stub_data,
    }
    return render(request, "Dashboard/claims.html", context)


def inspections(request):
    """Inspections page (WIP stub)."""
    if not _can_access_inspections(request.user):
        return HttpResponseForbidden("You don't have permission to view inspections.")

    wip_mode = True
    inspection_type_choices = [
        ("warranty", "Extended warranty"),
        ("claim", "Claim inspection"),
        ("other", "Other"),
    ]

    dealerships = [
        {"pk": 1, "name": "Default Dealership"},
        {"pk": 2, "name": "Northside Motors"},
        {"pk": 3, "name": "Westside Auto"},
    ]
    products = list(SalesProduct.objects.all()[:6])
    products_stub = [{"pk": p.pk, "name": p.name} for p in products]

    sample_appointments = [
        {
            "id": 1,
            "status": "scheduled",
            "dealership": dealerships[1],
            "product": products_stub[1] if len(products_stub) > 1 else (products_stub[0] if products_stub else {"pk": None, "name": "—"}),
            "appointment_time": timezone.now(),
            "request_number": "REQ-1001",
        }
    ]

    submitted_stub_data = None
    if request.method == "POST":
        submitted_stub_data = {
            "request_number": (request.POST.get("request_number") or "").strip(),
            "inspection_type": request.POST.get("inspection_type") or "",
            "dealership_id": request.POST.get("dealership_id") or "",
            "product_id": request.POST.get("product_id") or "",
            "appointment_time": (request.POST.get("appointment_time") or "").strip(),
            "inspector_name": (request.POST.get("inspector_name") or "").strip(),
            "notes": (request.POST.get("notes") or "").strip(),
        }
        messages.success(request, "Inspection booking received (WIP stub). No data was saved yet.")

    context = {
        "wip_mode": wip_mode,
        "inspection_type_choices": inspection_type_choices,
        "dealerships": dealerships,
        "products": products_stub,
        "sample_appointments": sample_appointments,
        "submitted_stub_data": submitted_stub_data,
    }
    return render(request, "Dashboard/inspections.html", context)


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