from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .models import EveItemTax


@override_settings(EVE_LOGIN_ENABLED=False)
class NavigationTests(TestCase):
    def test_shared_logo_and_staff_links_match_across_main_and_staff_pages(self):
        user=get_user_model().objects.create_user('nav-staff',is_staff=True)
        self.client.force_login(user)
        item=EveItemTax.objects.create(type_id=34,type_name='Tritanium',flat_cost=0)
        for path in ['/buyback/','/buyback/tax_edit/',f'/buyback/tax_edit/item/{item.pk}/','/buyback/staff/contracts/']:
            response=self.client.get(path,secure=True)
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'class="site-brand"')
            self.assertContains(response,'width="32" height="32"')
            self.assertContains(response,'site-header.css')
            self.assertContains(response,'href="/buyback/tax_edit/"')
            self.assertContains(response,'href="/buyback/staff/contracts/"')

    def test_guests_and_nonstaff_never_see_staff_navigation_and_routes_stay_protected(self):
        for user in [None,get_user_model().objects.create_user('nav-ordinary')]:
            self.client.logout()
            if user:self.client.force_login(user)
            for path in ['/buyback/','/buyback/?ui=legacy','/buyback/?ui=modern']:
                response=self.client.get(path,secure=True)
                self.assertNotContains(response,'href="/buyback/tax_edit/"')
                self.assertNotContains(response,'href="/buyback/staff/contracts/"')
                if 'ui=legacy' in path:
                    self.assertNotContains(response,'class="site-header"')
                    self.assertContains(response,'SPOOPY BUYBACK')
                else:
                    self.assertContains(response,'class="site-brand"')
            for path in ['/buyback/tax_edit/','/buyback/staff/contracts/']:
                self.assertEqual(self.client.get(path,secure=True).status_code,302)

    def test_old_ui_choice_persists_for_posts_and_can_be_reversed(self):
        response=self.client.get('/buyback/',secure=True)
        self.assertTemplateUsed(response,'buyback/index.html')
        self.assertContains(response,'Old UI')
        response=self.client.get('/buyback/?ui=legacy',secure=True)
        self.assertTemplateUsed(response,'buyback/legacy_index.html')
        self.assertContains(response,'New UI')
        self.assertNotContains(response,'class="site-header"')
        self.assertContains(response,'bg-srcgray-dark')
        self.assertContains(response,'buyback/buyback.png')
        item=EveItemTax.objects.create(type_id=34,type_name='Tritanium',flat_cost=0,jita_buy_percentage=.9)
        with patch('buyback.views.requests.post') as post:
            post.return_value.json.return_value=[{'itemType':{'eid':34,'name':'Tritanium','volume':.01},'immediatePrices':{'buyPrice5DayMedian':10}}]
            response=self.client.post('/buyback/',{'item_name':'Tritanium\t100'},secure=True)
        self.assertTemplateUsed(response,'buyback/legacy_index.html')
        self.assertEqual(response.context['totals_info'],[900,1000,90])
        response=self.client.get('/buyback/?ui=modern',secure=True)
        self.assertTemplateUsed(response,'buyback/index.html')
        self.assertEqual(self.client.session['buyback_ui'],'modern')
        self.client.get('/buyback/?ui=invalid',secure=True)
        self.assertEqual(self.client.session['buyback_ui'],'modern')


    @override_settings(EVE_LOGIN_ENABLED=True,EVE_SPECIAL_CORPORATION_ID=98472700,EVE_ALLIANCE_IDS=[99003214])
    @patch('buyback.eve_auth.character_affiliation',return_value={'corporation_id':98472700,'alliance_id':99003214})
    def test_navbar_displays_eve_name_and_logout_without_duplicate_page_controls(self,affiliation):
        session=self.client.session
        session['eve_character']={'id':123,'name':'Test Pilot'};session.save()
        response=self.client.get('/buyback/',secure=True)
        self.assertContains(response,'class="site-username"')
        self.assertContains(response,'Test Pilot')
        self.assertEqual(response.content.decode().count('action="/buyback/auth/eve/logout/"'),1)
        response=self.client.get('/buyback/?ui=legacy',secure=True)
        self.assertContains(response,'class="legacy-tools"')
        self.assertNotContains(response,'class="site-header"')
        self.assertContains(response,'Test Pilot')

    @override_settings(EVE_BUYBACK_CORPORATION_ID=98475239)
    def test_classic_theme_follows_staff_navigation_and_switches_on_current_page(self):
        from django.utils import timezone
        from .models import BuybackContract
        self.client.force_login(get_user_model().objects.create_user('theme-staff',is_staff=True))
        item=EveItemTax.objects.create(type_id=34,type_name='Tritanium',flat_cost=0)
        BuybackContract.objects.create(contract_id=123,corporation_id=98475239,
            data={'title':'Theme test','issuer_id':None},synced_at=timezone.now())
        self.client.get('/buyback/?ui=legacy',secure=True)
        paths=['/buyback/tax_edit/',f'/buyback/tax_edit/item/{item.pk}/',
               '/buyback/staff/contracts/','/buyback/staff/contracts/123/']
        for path in paths:
            response=self.client.get(path,secure=True)
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'class="classic-staff"')
            self.assertContains(response,'classic-staff.css')
            self.assertContains(response,'class="classic-banner"')
            self.assertContains(response,'New UI')
            self.assertNotContains(response,'class="site-header"')
            self.assertEqual(response.context['ui_switch_url'],path+'?ui=modern')
        response=self.client.get('/buyback/staff/contracts/?status=outstanding&ui=modern',secure=True)
        self.assertContains(response,'class="site-header"')
        self.assertNotContains(response,'classic-staff.css')
        self.assertEqual(response.context['ui_switch_url'],
            '/buyback/staff/contracts/?status=outstanding&ui=legacy')
        self.assertContains(self.client.get('/buyback/tax_edit/',secure=True),'class="site-header"')
        self.assertEqual(self.client.session['buyback_ui'],'modern')

    def test_theme_switch_retains_browse_filter_and_guest_protection(self):
        staff=get_user_model().objects.create_user('filter-theme-staff',is_staff=True)
        self.client.force_login(staff)
        response=self.client.get('/buyback/tax_edit/?q=Tritanium&review=1&page=2&ui=legacy',secure=True)
        self.assertContains(response,'class="classic-staff"')
        self.assertEqual(response.context['ui_switch_url'],
            '/buyback/tax_edit/?q=Tritanium&review=1&page=2&ui=modern')
        self.assertTrue(response.context['review_only'])
        self.client.logout()
        self.client.get('/buyback/?ui=legacy',secure=True)
        for path in ['/buyback/tax_edit/','/buyback/staff/contracts/']:
            response=self.client.get(path,secure=True)
            self.assertEqual(response.status_code,302)
            self.assertIn('/buyback/auth/staff/',response['Location'])
