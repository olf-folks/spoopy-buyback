from zipfile import ZipFile, BadZipFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from buyback.models import MarketGroup, MarketType
from .import_sde import read_table, english


class Command(BaseCommand):
    help = 'Load official market hierarchy and type links; never modify item rates.'

    def add_arguments(self, parser):
        parser.add_argument('archive')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        try:
            with ZipFile(options['archive']) as archive:
                groups = read_table(archive, 'marketGroups')
                types = read_table(archive, 'types')
            rows = []
            for key, group in groups.items():
                parent = group.get('parentGroupID')
                if parent is not None and parent not in groups:
                    raise ValueError(f'Missing market parent {parent}')
                seen = {key}
                ancestor = parent
                while ancestor is not None:
                    if ancestor in seen:
                        raise ValueError('Cycle in market hierarchy')
                    seen.add(ancestor)
                    ancestor = groups[ancestor].get('parentGroupID')
                rows.append(MarketGroup(id=key, name=english(group), parent_id=parent))
            mappings = []
            for key, item in types.items():
                group_id = item.get('marketGroupID')
                if group_id is not None:
                    if group_id not in groups:
                        raise ValueError(f'Missing market group {group_id} for type {key}')
                    mappings.append(MarketType(type_id=key, market_group_id=group_id))
        except (OSError, BadZipFile, KeyError, TypeError, ValueError) as exc:
            raise CommandError(f'Invalid market export: {exc}') from exc
        self.stdout.write(f'Market groups: {len(rows)}; type links: {len(mappings)}')
        if options['dry_run']:
            self.stdout.write('Dry run: no changes written.')
            return
        with transaction.atomic():
            MarketGroup.objects.bulk_create(rows, update_conflicts=True,
                update_fields=['name', 'parent'], unique_fields=['id'], batch_size=500)
            MarketType.objects.bulk_create(mappings, update_conflicts=True,
                update_fields=['market_group'], unique_fields=['type_id'], batch_size=500)
        self.stdout.write(self.style.SUCCESS('Market menu loaded. Item rates and fees unchanged.'))
