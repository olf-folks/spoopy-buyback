from django.core.management.base import BaseCommand
from buyback.models import EveItemTax

class Command(BaseCommand):
    help = 'Convert flat_cost entries from strings to integers'

    def handle(self, *args, **options):
        item_taxes = EveItemTax.objects.all()

        for item_tax in item_taxes:
            flat_cost_str = str(item_tax.flat_cost)
            flat_cost_int = int(flat_cost_str.replace(',', '')) if flat_cost_str else 0
            
            item_tax.flat_cost = flat_cost_int
            item_tax.save()
            self.stdout.write(self.style.SUCCESS(f'Successfully converted flat_cost for item tax {item_tax.taxid}'))

        self.stdout.write(self.style.SUCCESS('Finished converting flat_cost entries'))
