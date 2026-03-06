from django.shortcuts import render, redirect
from .forms import ReportForm
from .models import Report


def index(request):
    """The Dashboard for C3."""
    return render(request, "Dashboard/index.html")


def Reports(request):
    """Show all Reports."""
    reportlist = Report.objects.order_by("date_added")
    context = {"Reports": reportlist}
    return render(request, "Dashboard/Reports.html", context)


def report(request, report_id):
    """Show a single Report and its entries."""
    myreport = Report.objects.get(id=report_id)
    myentries = myreport.entry_set.order_by('-date_added')
    context = {'report': myreport, 'entries': myentries}
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
    #test