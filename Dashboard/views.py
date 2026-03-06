from decimal import Decimal, InvalidOperation

from django.db.models import Sum
from django.http import FileResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST
from .forms import ReportForm, EntryForm, SalesProductForm, DailySaleForm
from .models import Report, SalesProduct, DailySale, Entry, EntryDocument


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

        price = p.price or Decimal("0")
        goal_rev = Decimal(p.goal) * price
        achieved_units = min(sales_this_month, p.goal)
        achieved_rev = Decimal(achieved_units) * price
        revenue_goal += goal_rev
        revenue_achieved += achieved_rev

    if revenue_goal > 0:
        revenue_goal_pct = (revenue_achieved / revenue_goal) * Decimal("100")
    else:
        revenue_goal_pct = Decimal("0")

    # Clamp for chart display
    if revenue_goal_pct < 0:
        revenue_goal_pct = Decimal("0")
    if revenue_goal_pct > 100:
        revenue_goal_pct = Decimal("100")

    context = {
        "dashboard_rows": dashboard_rows,
        "revenue_goal_pct": float(revenue_goal_pct),
        "revenue_goal": f"{revenue_goal.quantize(Decimal('0.01'))}",
        "revenue_achieved": f"{revenue_achieved.quantize(Decimal('0.01'))}",
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
    ).select_related("product").order_by("-date", "-id")
    context = {
        "sales_products": products,
        "daily_sales_this_month": daily_sales_this_month,
        "add_form": SalesProductForm(),
        "add_daily_form": DailySaleForm(),
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
    form = DailySaleForm(request.POST)
    if form.is_valid():
        form.save()
    return redirect("Dashboard:sales")


def sales_edit_daily(request, daily_pk):
    """Edit a daily sale. Allowed only for admin, Sales Rep, Dealership User."""
    if not _can_modify_daily_sales(request.user):
        return HttpResponseForbidden("You don't have permission to edit daily sales.")
    obj = get_object_or_404(DailySale, pk=daily_pk)
    if request.method == "POST":
        form = DailySaleForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("Dashboard:sales")
    else:
        form = DailySaleForm(instance=obj)
    context = {"form": form, "daily_sale": obj}
    return render(request, "Dashboard/sales_edit_daily.html", context)


@require_POST
def sales_delete_daily(request, daily_pk):
    """Delete a daily sale. Allowed only for admin, Sales Rep, Dealership User."""
    if not _can_modify_daily_sales(request.user):
        return HttpResponseForbidden("You don't have permission to delete daily sales.")
    obj = get_object_or_404(DailySale, pk=daily_pk)
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