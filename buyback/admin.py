from django.contrib import admin
from .models import EveItemTax
from .filters import GroupNameFilter

class EveItemTaxAdmin(admin.ModelAdmin):
    search_fields = ['type_name', 'type_id', 'group']
    list_display = ['type_name', 'type_id', 'group', 'jita_buy_percentage', 'flat_cost', 'hauling_fee']
    # list_filter = ['group_id']
    list_filter = ['group']
    readonly_fields = ['group_id', 'type_name', 'type_id']  # Make the group_id, type_name, and type_id fields read-only

    
    def group_name(self, obj):
        return obj.group.name if obj.group else ''
    group_name.short_description = 'Group Name'

admin.site.register(EveItemTax, EveItemTaxAdmin)
