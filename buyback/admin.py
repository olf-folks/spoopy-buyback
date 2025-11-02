from django.contrib import admin
from .models import EveItemTax
#from .filters import GroupNameFilter
from django.utils.html import format_html
from django.db.models import DecimalField
from decimal import Decimal



class NewItemFilter(admin.SimpleListFilter):
    title = 'NewItems'
    parameter_name = 'jita_buy_percentage'

    def lookups(self, request, model_admin):
        return [
            ('0.8555', '0.8555'),
        ]

    def queryset(self, request, queryset):
        if self.value() is not None:
            # Convert the filter value to a Decimal object
            filter_value = Decimal(self.value())
            # Use the DecimalField lookup to filter based on exact value
            return queryset.filter(jita_buy_percentage=filter_value)
        return queryset


class EveItemTaxAdmin(admin.ModelAdmin):
    search_fields = ['type_name', 'type_id', 'group']
    list_display = ['type_name', 'type_id', 'group', 'jita_buy_percentage', 'flat_cost', 'hauling_fee', 'needs_review']
    # list_filter = ['group_id']
    list_filter = [ NewItemFilter, 'group', 'needs_review']
    #readonly_fields = ['group_id', 'category_id', 'category_name', 'type_name', 'group', 'type_id']  # Make the group_id, type_name, and type_id fields read-only
    #readonly_fields = ['group_id', 'category_id', 'category_name', 'type_name', 'group']  # able to edit type_id

    class Media:
        css = {
            'all': ('admin.css',),
        }
       
    def group_name(self, obj):
        return obj.group.name if obj.group else ''
    group_name.short_description = 'Group Name'

admin.site.register(EveItemTax, EveItemTaxAdmin)
