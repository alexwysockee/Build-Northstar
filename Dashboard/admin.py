from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Report, Entry

#test
# Custom User admin so Groups are easy to assign in the admin
class UserAdmin(BaseUserAdmin):
    filter_horizontal = ("groups", "user_permissions")


admin.site.unregister(User)
admin.site.register(User, UserAdmin)

admin.site.register(Report)
admin.site.register(Entry)