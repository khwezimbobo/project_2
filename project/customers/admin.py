from django.contrib import admin

from .models import Customer

# Register your models here.
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'address', 'agent', 'created_at', 'updated_at')
    search_fields = ('name', 'email', 'phone', 'address', 'agent__username')
    list_filter = ('agent', 'created_at', 'updated_at')