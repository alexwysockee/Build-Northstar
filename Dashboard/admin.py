from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Dealership, Report, Entry, SalesProduct, DailySale, EntryDocument

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
admin.site.register(DailySale)


@admin.register(Dealership)
class DealershipAdmin(admin.ModelAdmin):
    list_display = ("name", "badge_css_class", "is_default_home")
    list_filter = ("is_default_home",)
    search_fields = ("name",)