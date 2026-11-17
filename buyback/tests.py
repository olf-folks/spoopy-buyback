from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import EveItemTax


@override_settings(EVE_LOGIN_ENABLED=False)
class DeploymentSmokeTests(TestCase):
    def test_public_pages_and_admin_login(self):
        response = self.client.get('/', secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/buyback/')
        self.assertEqual(self.client.get('/buyback/', secure=True).status_code, 200)
        self.assertEqual(self.client.get('/admin/login/', secure=True).status_code, 200)
        self.assertEqual(self.client.get('/buyback/tax_edit/', secure=True).status_code, 302)

    @patch('buyback.views.requests.post')
    def test_appraisal_preserves_configured_rate(self, post):
        EveItemTax.objects.create(type_id=34, type_name='Tritanium',
                                  jita_buy_percentage=0.9, flat_cost=0)
        post.return_value.json.return_value = [{
            'itemType': {'eid': 34, 'name': 'Tritanium', 'volume': 0.01},
            'immediatePrices': {'buyPrice5DayMedian': 10},
        }]
        response = self.client.post(reverse('buyback:index'),
                                    {'item_name': 'Tritanium\t100'}, secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['totals_info'], [900, 1000, 90])
        self.assertEqual(post.call_args.kwargs['timeout'], 30)


class SDEImportTests(TestCase):
    def archive(self, directory, broken=False):
        import json
        from pathlib import Path
        from zipfile import ZipFile
        path = Path(directory) / 'sde.zip'
        tables = {
            'types': [
                {'_key': 34, 'groupID': 18, 'name': {'en': 'Tritanium'}, 'published': True},
                {'_key': 35, 'groupID': 999 if broken else 18, 'name': {'en': 'Pyerite'}, 'published': True},
                {'_key': 36, 'groupID': 18, 'name': {'en': 'Hidden'}, 'published': False},
            ],
            'groups': [{'_key': 18, 'categoryID': 4, 'name': {'en': 'Mineral'}}],
            'categories': [{'_key': 4, 'name': {'en': 'Material'}}],
        }
        with ZipFile(path, 'w') as archive:
            for table, rows in tables.items():
                archive.writestr(table + '.jsonl', '\n'.join(json.dumps(row) for row in rows))
        return str(path)

    def test_import_preserves_pricing_is_repeatable_and_dry_run_is_read_only(self):
        import tempfile
        from decimal import Decimal
        from django.core.management import call_command
        row = EveItemTax.objects.create(type_id=34, type_name='Old name',
            flat_cost=Decimal('42.50'), jita_buy_percentage=0.91,
            hauling_fee=True, needs_review=False)
        with tempfile.TemporaryDirectory() as directory:
            archive = self.archive(directory)
            call_command('import_sde', archive, dry_run=True)
            row.refresh_from_db()
            self.assertEqual(row.type_name, 'Old name')
            self.assertEqual(EveItemTax.objects.count(), 1)
            call_command('import_sde', archive)
            call_command('import_sde', archive)
        row.refresh_from_db()
        self.assertEqual(EveItemTax.objects.count(), 2)
        self.assertEqual((row.flat_cost, row.jita_buy_percentage, row.hauling_fee,
                          row.needs_review), (Decimal('42.50'), 0.91, True, False))
        self.assertEqual((row.group_id, row.category_id, row.needs_update), (18, 4, False))
        new = EveItemTax.objects.get(type_id=35)
        self.assertEqual((new.flat_cost, new.jita_buy_percentage, new.needs_review,
                          new.needs_update), (0, 0, True, False))
        self.assertFalse(EveItemTax.objects.filter(type_id=36).exists())

    def test_invalid_references_leave_database_unchanged(self):
        import tempfile
        from django.core.management import call_command, CommandError
        EveItemTax.objects.create(type_id=34, type_name='Original', flat_cost=10)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(CommandError):
                call_command('import_sde', self.archive(directory, broken=True))
        self.assertEqual(EveItemTax.objects.count(), 1)
        self.assertEqual(EveItemTax.objects.get(type_id=34).type_name, 'Original')


class CatalogPaginationTests(TestCase):
    def test_large_catalog_pages_are_bounded_and_tree_renders(self):
        EveItemTax.objects.bulk_create([EveItemTax(type_id=i, type_name=f'Item {i:03}',
            group_id=18, group='Mineral', category_id=4, category_name='Material',
            flat_cost=0) for i in range(205)])
        for url in ['/buyback/all_item_tax/', '/buyback/collapsible_tree/']:
            response = self.client.get(url, secure=True)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.context['page_obj']), 200)
            self.assertEqual(response.context['page_obj'].paginator.count, 205)
            response = self.client.get(url + '?page=2', secure=True)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.context['page_obj']), 5)


class MarketEditorTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from .models import MarketGroup, MarketType
        self.staff = get_user_model().objects.create_user('editor', is_staff=True)
        self.client.force_login(self.staff)
        self.root = MarketGroup.objects.create(id=4, name='Ships')
        self.child = MarketGroup.objects.create(id=5, name='Frigates', parent=self.root)
        self.leaf = MarketGroup.objects.create(id=6, name='Standard Frigates', parent=self.child)
        self.other = MarketGroup.objects.create(id=10, name='Minerals')
        self.ship = EveItemTax.objects.create(type_id=100, type_name='Magnate', flat_cost=0, jita_buy_percentage=0.9)
        self.mineral = EveItemTax.objects.create(type_id=34, type_name='Tritanium', flat_cost=42, jita_buy_percentage=0.9)
        self.unlisted = EveItemTax.objects.create(type_id=999, type_name='Unlisted item', flat_cost=0)
        MarketType.objects.create(type_id=100, market_group=self.leaf)
        MarketType.objects.create(type_id=34, market_group=self.other)

    def test_tree_branch_breadcrumbs_and_rate_display(self):
        response = self.client.get('/buyback/tax_edit/market/4/', secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Standard Frigates')
        self.assertContains(response, '90%')
        self.assertContains(response, 'Magnate')
        self.assertNotContains(response, 'Tritanium</a>')
        self.assertEqual(response.context['total'], 1)
        self.assertTrue(response.context['market_tree'][1]['open'])
        response = self.client.get('/buyback/tax_edit/market/6/', secure=True)
        self.assertEqual([c['name'] for c in response.context['breadcrumbs']], ['Ships', 'Frigates', 'Standard Frigates'])

    def test_review_dots_propagate_to_ancestors_and_clear_after_bulk_review(self):
        self.ship.needs_review=True
        self.ship.save()
        response=self.client.get('/buyback/tax_edit/market/4/',secure=True)
        self.assertContains(response,'class="review-dot"')
        self.assertEqual(response.context['all_review_count'],1)
        filtered=self.client.get('/buyback/tax_edit/market/4/?review=1',secure=True)
        self.assertEqual(list(filtered.context['page_obj']),[self.ship])
        self.assertContains(filtered,'/buyback/tax_edit/market/6/?review=1')
        ships=next(node for node in response.context['market_tree'] if node['id']==4)
        minerals=next(node for node in response.context['market_tree'] if node['id']==10)
        self.assertEqual(ships['review_count'],1)
        self.assertEqual(ships['children'][0]['review_count'],1)
        self.assertEqual(ships['children'][0]['children'][0]['review_count'],1)
        self.assertEqual(minerals['review_count'],0)
        self.client.post('/buyback/tax_edit/market/4/?review=1',{'action':'review','needs_review':'false'},secure=True)
        response=self.client.get('/buyback/tax_edit/market/4/',secure=True)
        self.assertNotContains(response,'class="review-dot"')
        self.unlisted.needs_review=True
        self.unlisted.save()
        response=self.client.get('/buyback/tax_edit/?unlisted=1',secure=True)
        self.assertEqual(response.context['unlisted_review_count'],1)
        self.assertContains(response,'Needs review: 1 item')

    def test_review_status_selection_matches_saved_items_on_reload(self):
        url='/buyback/tax_edit/market/4/'
        response=self.client.get(url,secure=True)
        self.assertEqual(response.context['review_form']['needs_review'].value(),'false')
        self.assertContains(response,'<option value="false" selected>Reviewed</option>',html=True)
        self.client.post(url,{'action':'review','needs_review':'true'},secure=True)
        response=self.client.get(url,secure=True)
        self.assertEqual(response.context['review_form']['needs_review'].value(),'true')
        self.assertContains(response,'<option value="true" selected>Needs review</option>',html=True)
        self.client.post(url,{'action':'review','needs_review':'false'},secure=True)
        response=self.client.get(url,secure=True)
        self.assertEqual(response.context['review_form']['needs_review'].value(),'false')
        self.ship.refresh_from_db()
        self.assertFalse(self.ship.needs_review)
        self.mineral.needs_review=True
        self.mineral.save()
        response=self.client.get('/buyback/tax_edit/',secure=True)
        self.assertEqual(response.context['review_form']['needs_review'].value(),'')
        before=list(EveItemTax.objects.order_by('pk').values())
        response=self.client.post('/buyback/tax_edit/',{'action':'review','needs_review':''},secure=True)
        self.assertEqual(response.status_code,200)
        self.assertEqual(before,list(EveItemTax.objects.order_by('pk').values()))
        item_page=self.client.get(f'/buyback/tax_edit/item/{self.ship.pk}/',secure=True)
        self.assertFalse(item_page.context['item_form']['needs_review'].value())

    def test_rate_change_is_percent_scoped_and_preserves_flat_price(self):
        response = self.client.post('/buyback/tax_edit/market/4/',
            {'action': 'rate', 'jita_buy_percentage': '85'}, secure=True)
        self.assertEqual(response.status_code, 302)
        self.ship.refresh_from_db()
        self.mineral.refresh_from_db()
        self.assertEqual(self.ship.jita_buy_percentage, 0.85)
        self.assertEqual(self.mineral.jita_buy_percentage, 0.9)
        self.assertEqual(self.mineral.flat_cost, 42)
        response = self.client.post('/buyback/tax_edit/market/4/',
            {'action': 'rate', 'jita_buy_percentage': '101'}, secure=True)
        self.assertEqual(response.status_code, 200)
        self.ship.refresh_from_db()
        self.assertEqual(self.ship.jita_buy_percentage, 0.85)

    def test_search_unlisted_and_access(self):
        response = self.client.get('/buyback/tax_edit/?q=34', secure=True)
        self.assertEqual(list(response.context['page_obj']), [self.mineral])
        response = self.client.get('/buyback/tax_edit/?unlisted=1', secure=True)
        self.assertEqual(list(response.context['page_obj']), [self.unlisted])
        self.assertEqual(self.client.get('/buyback/tax_edit/market/456/', secure=True).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get('/buyback/tax_edit/', secure=True).status_code, 302)
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user('regular')
        self.client.force_login(user)
        self.assertEqual(self.client.post('/buyback/tax_edit/market/4/',
            {'action':'rate', 'jita_buy_percentage':'10'}, secure=True).status_code, 302)
        self.ship.refresh_from_db()
        self.assertEqual(self.ship.jita_buy_percentage, 0.9)

    def test_bulk_change_includes_items_on_other_pages_and_respects_search(self):
        from .models import MarketType
        rows = [EveItemTax(type_id=1000+i, type_name=f'Other ship {i:03}',
                          flat_cost=0, jita_buy_percentage=0.9) for i in range(105)]
        EveItemTax.objects.bulk_create(rows)
        MarketType.objects.bulk_create([MarketType(type_id=row.type_id, market_group=self.leaf) for row in rows])
        response = self.client.get('/buyback/tax_edit/market/4/', secure=True)
        self.assertEqual(len(response.context['page_obj']), 100)
        self.client.post('/buyback/tax_edit/market/4/?q=Other',
            {'action': 'rate', 'jita_buy_percentage': '75'}, secure=True)
        self.assertEqual(EveItemTax.objects.filter(jita_buy_percentage=0.75).count(), 105)
        self.ship.refresh_from_db()
        self.assertEqual(self.ship.jita_buy_percentage, 0.9)

    def test_item_editor_saves_only_item_and_returns_to_selection(self):
        from urllib.parse import urlencode
        target = '/buyback/tax_edit/market/4/?q=Magnate&page=2'
        url = f'/buyback/tax_edit/item/{self.ship.pk}/?' + urlencode({'next': target})
        response = self.client.get(url, secure=True)
        self.assertContains(response, 'Save and return')
        self.assertContains(response, 'Market categories')
        self.assertEqual(response.context['item_form'].initial['jita_buy_percentage'], 90)
        response = self.client.post(url, {'corp_jita_buy_percentage':'85', 'outsider_jita_buy_percentage':'85', 'jita_buy_percentage': '82.5', 'flat_cost': '12.50',
            'hauling_fee': 'on', 'needs_review': 'on'}, secure=True)
        self.assertEqual(response['Location'], target)
        self.ship.refresh_from_db()
        self.mineral.refresh_from_db()
        self.assertEqual(self.ship.jita_buy_percentage, 0.825)
        self.assertEqual(str(self.ship.flat_cost), '12.50')
        self.assertTrue(self.ship.hauling_fee)
        self.assertTrue(self.ship.needs_review)
        self.assertEqual(self.ship.type_id, 100)
        self.assertEqual(self.mineral.flat_cost, 42)
        response = self.client.get('/buyback/tax_edit/market/4/', secure=True)
        self.assertContains(response, f'/buyback/tax_edit/item/{self.ship.pk}/?next=')
        self.assertNotContains(response, f'/admin/buyback/eveitemtax/{self.ship.pk}/change/')

    def test_item_editor_validation_access_and_safe_return(self):
        url = f'/buyback/tax_edit/item/{self.ship.pk}/?next=https://example.com/'
        response = self.client.post(url, {'corp_jita_buy_percentage':'85', 'outsider_jita_buy_percentage':'85', 'jita_buy_percentage': '101', 'flat_cost': '-1'}, secure=True)
        self.assertEqual(response.status_code, 200)
        self.ship.refresh_from_db()
        self.assertEqual(self.ship.jita_buy_percentage, 0.9)
        response = self.client.post(url, {'corp_jita_buy_percentage':'85', 'outsider_jita_buy_percentage':'85', 'jita_buy_percentage': '80', 'flat_cost': '0'}, secure=True)
        self.assertEqual(response['Location'], '/buyback/tax_edit/market/6/')
        self.assertEqual(self.client.get('/buyback/tax_edit/item/999999/', secure=True).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.post(url, {'corp_jita_buy_percentage':'85', 'outsider_jita_buy_percentage':'85', 'jita_buy_percentage': '10', 'flat_cost': '0'}, secure=True).status_code, 302)
        self.ship.refresh_from_db()
        self.assertEqual(self.ship.jita_buy_percentage, 0.8)

    def test_bulk_review_status_across_pages_and_scoped_search(self):
        from .models import MarketType
        rows = [EveItemTax(type_id=2000+i, type_name=f'Review ship {i:03}',
            flat_cost=0, needs_review=True) for i in range(105)]
        EveItemTax.objects.bulk_create(rows)
        MarketType.objects.bulk_create([MarketType(type_id=row.type_id, market_group=self.leaf) for row in rows])
        self.client.post('/buyback/tax_edit/market/4/?q=Review',
            {'action': 'review', 'needs_review': 'false'}, secure=True)
        self.assertFalse(EveItemTax.objects.filter(type_name__startswith='Review', needs_review=True).exists())
        self.client.post('/buyback/tax_edit/market/4/',
            {'action': 'review', 'needs_review': 'true'}, secure=True)
        self.assertEqual(EveItemTax.objects.filter(needs_review=True).count(), 106)
        response = self.client.post('/buyback/tax_edit/market/4/',
            {'action': 'review', 'needs_review': 'invalid'}, secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(EveItemTax.objects.filter(needs_review=True).count(), 106)
        self.mineral.refresh_from_db()
        self.assertFalse(self.mineral.needs_review)

    def test_market_import_is_repeatable_and_does_not_modify_business_rows(self):
        import tempfile, json
        from pathlib import Path
        from zipfile import ZipFile
        from django.core.management import call_command, CommandError
        from .models import MarketGroup, MarketType
        before = list(EveItemTax.objects.order_by('taxid').values())
        with tempfile.TemporaryDirectory() as directory:
            archive = str(Path(directory) / 'market.zip')
            with ZipFile(archive, 'w') as z:
                z.writestr('marketGroups.jsonl', '\n'.join(json.dumps(row) for row in [
                    {'_key': 20, 'name': {'en': 'New category'}},
                    {'_key': 21, 'parentGroupID': 20, 'name': {'en': 'New subcategory'}}]))
                z.writestr('types.jsonl', json.dumps({'_key': 34, 'marketGroupID': 21}))
            call_command('import_market_menu', archive, dry_run=True)
            self.assertFalse(MarketGroup.objects.filter(pk=20).exists())
            call_command('import_market_menu', archive)
            call_command('import_market_menu', archive)
            self.assertEqual(MarketType.objects.get(type_id=34).market_group_id, 21)
            self.assertEqual(MarketGroup.objects.get(pk=21).parent_id, 20)
            with ZipFile(archive, 'w') as z:
                z.writestr('marketGroups.jsonl', json.dumps({'_key':20, 'parentGroupID':20, 'name':{'en':'Cycle'}}))
                z.writestr('types.jsonl', '')
            with self.assertRaises(CommandError):
                call_command('import_market_menu', archive)
        self.assertEqual(before, list(EveItemTax.objects.order_by('taxid').values()))
