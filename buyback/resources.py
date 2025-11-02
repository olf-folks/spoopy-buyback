from import_export import resources
from .models import EveItemTax

class EveItemTaxResource(resources.ModelResource):
    class Meta:
        model = EveItemTax
        fields = ('type_id', 'group_id', 'type_name', 'jita_buy_percentage', 'flat_cost', 'hauling_fee')  # List all fields to import