from django.contrib import admin

# Register your models here.


from django.contrib import admin
from .models import EveItemTax




# admin.site.register(EveItemTax)


class EveItemTaxAdmin(admin.ModelAdmin):
    search_fields = ['type_name', 'type_id', 'group_id']  # Add any other fields you want to search

# Register your model with the custom admin class
admin.site.register(EveItemTax, EveItemTaxAdmin)