from django.contrib import admin
from .models import EveItemTax

class EveItemTaxAdmin(admin.ModelAdmin):
    search_fields = ['type_name', 'type_id', 'group_id']
    list_display = ['type_name', 'type_id', 'group_id', 'jita_buy_percentage']
    list_filter = ['group_id']

    # Define a custom action to batch edit the jita_buy_percentage for an entire group
    def batch_edit_jita_buy_percentage(self, request, queryset):
        selected_group_id = queryset.first().group_id
        new_jita_buy_percentage = float(request.POST.get('new_jita_buy_percentage'))
        
        # Update the jita_buy_percentage for the selected group
        EveItemTax.objects.filter(group_id=selected_group_id).update(jita_buy_percentage=new_jita_buy_percentage)
    
    batch_edit_jita_buy_percentage.short_description = "Batch Edit Jita Buy Percentage"

    # Add the custom action to the actions list
    actions = [batch_edit_jita_buy_percentage]

admin.site.register(EveItemTax, EveItemTaxAdmin)
