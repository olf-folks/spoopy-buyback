from django.core.management.base import BaseCommand, CommandError

from buyback.contracts import safe_error, sync_contracts
from buyback.models import ContractConnection


class Command(BaseCommand):
    help = 'Sync incoming Spoopy Buyback corporation item-exchange contracts (read-only ESI).'

    def handle(self, *args, **options):
        if not ContractConnection.objects.filter(pk=1).exists():
            self.stdout.write('No corporation authorization connected; nothing to sync.')
            return
        try:
            count = sync_contracts()
        except Exception as exc:
            raise CommandError(safe_error(exc)) from None
        self.stdout.write(f'Synced {count} incoming contracts.')
