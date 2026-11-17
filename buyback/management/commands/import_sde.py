"""Load CCP catalog metadata without replacing operator pricing settings."""
import json
from zipfile import ZipFile, BadZipFile

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from buyback.models import EveItemTax

METADATA = ['type_name', 'group_id', 'group', 'category_id', 'category_name', 'needs_update']


def read_table(archive, name):
    with archive.open(name + '.jsonl') as stream:
        rows = {}
        for line in stream:
            row = json.loads(line)
            key = row['_key']
            if key in rows:
                raise ValueError(f'Duplicate {name} key: {key}')
            rows[key] = row
        return rows


def english(row):
    value = row['name']['en']
    if not isinstance(value, str) or not value or len(value) > 255:
        raise ValueError('Missing or overlong English name')
    return value


class Command(BaseCommand):
    help = 'Import published item metadata from CCP JSONL SDE ZIP; preserve pricing and flags.'

    def add_arguments(self, parser):
        parser.add_argument('archive')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        try:
            with ZipFile(options['archive']) as archive:
                types = read_table(archive, 'types')
                groups = read_table(archive, 'groups')
                categories = read_table(archive, 'categories')
            # Validate the complete input before any writes. Include unpublished
            # metadata only for existing rows; never delete existing records.
            metadata = {}
            for type_id, item in types.items():
                group = groups[item['groupID']]
                category = categories[group['categoryID']]
                metadata[type_id] = dict(type_name=english(item),
                    group_id=item['groupID'], group=english(group),
                    category_id=group['categoryID'], category_name=english(category),
                    needs_update=False)
        except (OSError, BadZipFile, KeyError, ValueError, TypeError) as exc:
            raise CommandError(f'Invalid SDE archive: {exc}') from exc

        with transaction.atomic():
            # Serialize with web inserts and the API updater during the short
            # database write, so concurrent appraisals cannot create duplicates.
            if connection.vendor == 'postgresql':
                with connection.cursor() as cursor:
                    cursor.execute('LOCK TABLE buyback_eveitemtax IN SHARE ROW EXCLUSIVE MODE')
            existing = list(EveItemTax.objects.all())
            ids = {item.type_id for item in existing}
            updates = []
            for item in existing:
                values = metadata.get(item.type_id)
                if values and any(getattr(item, field) != value for field, value in values.items()):
                    for field, value in values.items():
                        setattr(item, field, value)
                    updates.append(item)
            new = [EveItemTax(type_id=type_id, **metadata[type_id],
                    jita_buy_percentage=0, flat_cost=0, hauling_fee=False, needs_review=True)
                   for type_id, item in types.items()
                   if item.get('published') is True and type_id not in ids]
            self.stdout.write(f'Existing rows: {len(existing)}; metadata updates: {len(updates)}; new published items: {len(new)}')
            self.stdout.write(f'Existing rows absent from SDE (preserved): {sum(item.type_id not in metadata for item in existing)}')
            if options['dry_run']:
                self.stdout.write('Dry run: no changes written.')
                return
            EveItemTax.objects.bulk_update(updates, METADATA, batch_size=500)
            EveItemTax.objects.bulk_create(new, batch_size=500)
        self.stdout.write(self.style.SUCCESS('Import committed. Existing pricing, fees, review flags and accounts preserved.'))
