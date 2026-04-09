from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Claim, Dealership, Report, Entry, SalesProduct, DailySale, EntryDocument

#test
# Custom User admin so Groups are easy to assign in the admin
class UserAdmin(BaseUserAdmin):
    filter_horizontal = ("groups", "user_permissions")


admin.site.unregister(User)
admin.site.register(User, UserAdmin)

admin.site.register(Report)
admin.site.register(Entry)
admin.site.register(EntryDocument)
admin.site.register(SalesProduct)


@admin.register(DailySale)
class DailySaleAdmin(admin.ModelAdmin):
    list_display = ("id", "order_number", "product", "dealership", "date", "amount")
    search_fields = ("order_number", "product__name", "dealership__name")
    list_filter = ("dealership", "date")


@admin.register(Dealership)
class DealershipAdmin(admin.ModelAdmin):
    list_display = ("name", "badge_css_class", "is_default_home")
    list_filter = ("is_default_home",)
    search_fields = ("name",)


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer_name",
        "daily_sale",
        "sale_dealership",
        "sale_product",
        "quantity",
        "status",
        "date_submitted",
        "submitted_by",
    )
    list_filter = ("status", "daily_sale__dealership")
    search_fields = ("customer_name", "reason", "daily_sale__order_number")
    autocomplete_fields = ("daily_sale",)
    readonly_fields = ("date_submitted",)

    @admin.display(description="Dealership")
    def sale_dealership(self, obj):
        return obj.daily_sale.dealership.name if obj.daily_sale_id else "—"

    @admin.display(description="Product")
    def sale_product(self, obj):
        return obj.daily_sale.product.name if obj.daily_sale_id else "—"