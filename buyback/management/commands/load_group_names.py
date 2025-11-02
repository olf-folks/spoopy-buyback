from django.core.management.base import BaseCommand
import requests
import requests_cache
from buyback.models import EveItemTax

class Command(BaseCommand):
    help = 'Load group names from the API and update the database'

    def handle(self, *args, **options):
        # Enable caching with a cache duration of 3600 seconds (1 hour)
        requests_cache.install_cache('group_cache', expire_after=3600)

        item_taxes = EveItemTax.objects.all()

        for item_tax in item_taxes:
            group_id = item_tax.group_id
            group_info = requests.get(f"https://esi.evetech.net/latest/universe/groups/{group_id}/").json()
            group_name = group_info['name']
            item_tax.group = group_name
            item_tax.save()
            self.stdout.write(self.style.SUCCESS(f'Successfully updated group name for group ID {group_id}'))

        self.stdout.write(self.style.SUCCESS('Finished updating group names'))
