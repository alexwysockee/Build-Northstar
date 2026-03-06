from django.urls import path

from . import views

app_name = "Dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.index, name="index"),
    path("product/<int:product_id>/", views.product, name="product"),
    path("sales/", views.sales, name="sales"),
    path("sales/add/", views.sales_add_product, name="sales_add_product"),
    path("sales/add-daily/", views.sales_add_daily, name="sales_add_daily"),
    path("sales/daily/<int:daily_pk>/edit/", views.sales_edit_daily, name="sales_edit_daily"),
    path("sales/daily/<int:daily_pk>/delete/", views.sales_delete_daily, name="sales_delete_daily"),
    path("sales/<int:product_pk>/update/", views.sales_update_product, name="sales_update_product"),
    path("sales/<int:product_pk>/delete/", views.sales_delete_product, name="sales_delete_product"),
    path("reports/", views.Reports, name="Reports"),
    path("reports/<int:report_id>/", views.report, name="report"),
    path("reports/<int:report_id>/delete/", views.delete_report, name="delete_report"),
    path("new_report/", views.new_report, name="new_report"),
    path("new_entry/<int:report_id>/", views.new_entry, name="new_entry"),
    path("entry/<int:entry_id>/edit/", views.edit_entry, name="edit_entry"),
    path("entry/<int:entry_id>/delete/", views.delete_entry, name="delete_entry"),
    path("entry/document/<int:doc_id>/delete/", views.delete_entry_document, name="delete_entry_document"),
    path("entry/document/<int:doc_id>/", views.entry_document_inline, name="entry_document_inline"),
]
