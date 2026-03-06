from django.urls import path

from . import views

app_name = "Dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("reports/", views.Reports, name="Reports"),
    path('reports/<int:report_id>/', views.report, name='report'),
    path('new_report/', views.new_report, name='new_report'),
]
#test