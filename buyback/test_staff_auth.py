from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
import requests

from .models import EveStaffIdentity
from .test_eve_auth import METADATA


@override_settings(EVE_STAFF_AUTH_ENABLED=True,EVE_LOGIN_ENABLED=True,
    EVE_BUYBACK_CORPORATION_ID=98475239,EVE_SPECIAL_CORPORATION_ID=98472700,
    EVE_ALLIANCE_IDS=[99003214],EVE_SSO_CLIENT_ID='test-client',
    EVE_SSO_CALLBACK_URL='https://buyback.spoopy.net/buyback/auth/eve/callback/')
class EveStaffAuthTests(TestCase):
    def setUp(self):
        patcher=patch('buyback.eve_auth.character_affiliation',return_value={'corporation_id':98475239,'alliance_id':None})
        self.affiliation=patcher.start();self.addCleanup(patcher.stop)
        meta=patch('buyback.eve_auth.sso_metadata',return_value=METADATA)
        meta.start();self.addCleanup(meta.stop)
        self.claims={'sub':'CHARACTER:EVE:12345','name':'Buyback Toon'}

    def authenticated_staff(self):
        user=get_user_model().objects.create_user('eve-staff',is_staff=True)
        EveStaffIdentity.objects.create(character_id=12345,user=user,character_name='Buyback Toon')
        self.client.force_login(user)
        session=self.client.session
        session['eve_character']={'id':12345,'name':'Buyback Toon'}
        session['buyback_ui']='legacy';session.save()
        return user

    def callback(self, claims=None):
        self.client.get(reverse('buyback:eve-login')+'?next=/buyback/tax_edit/',secure=True)
        state=self.client.session['eve_oauth']['state']
        with patch('buyback.eve_auth.requests.post') as post, patch('buyback.eve_auth.verified_claims',return_value=claims or self.claims):
            post.return_value.json.return_value={'access_token':'discarded-token'}
            return self.client.get(reverse('buyback:eve-callback'),{'state':state,'code':'code'},secure=True)

    def test_verified_buyback_toon_gets_basic_staff_login_and_retains_theme(self):
        session=self.client.session;session['buyback_ui']='legacy';session.save()
        response=self.callback()
        self.assertRedirects(response,'/buyback/tax_edit/',fetch_redirect_response=False)
        identity=EveStaffIdentity.objects.get(pk=12345)
        user=identity.user
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(set(user.user_permissions.values_list('codename',flat=True)),{'view_eveitemtax','change_eveitemtax'})
        self.assertEqual(str(user.pk),self.client.session['_auth_user_id'])
        self.assertEqual(self.client.session['buyback_ui'],'legacy')
        self.assertEqual(self.client.get('/buyback/tax_edit/',secure=True).status_code,200)
        self.assertContains(self.client.get('/buyback/',secure=True),'href="/buyback/tax_edit/"')
        self.callback()
        self.assertEqual(EveStaffIdentity.objects.count(),1)
        self.assertEqual(get_user_model().objects.count(),1)

    def test_spoopy_newbies_and_alliance_members_do_not_receive_staff(self):
        for corp in [98472700,123]:
            self.affiliation.return_value={'corporation_id':corp,'alliance_id':99003214}
            self.callback()
            self.assertNotIn('_auth_user_id',self.client.session)
            self.assertFalse(EveStaffIdentity.objects.exists())
            response=self.client.get('/buyback/',secure=True)
            self.assertNotContains(response,'href="/buyback/tax_edit/"')
            self.assertEqual(self.client.get('/buyback/staff/contracts/',secure=True).status_code,302)

    def test_leaving_corporation_revokes_access_on_next_request(self):
        user=self.authenticated_staff()
        self.assertEqual(self.client.get('/buyback/tax_edit/',secure=True).status_code,200)
        self.affiliation.return_value={'corporation_id':98472700,'alliance_id':99003214}
        response=self.client.get('/buyback/tax_edit/',secure=True)
        self.assertEqual(response.status_code,302)
        user.refresh_from_db();self.assertFalse(user.is_staff)
        self.assertNotContains(self.client.get('/buyback/',secure=True),'href="/buyback/staff/contracts/"')

    def test_esi_outage_denies_staff_without_permanently_revoking_account(self):
        user=self.authenticated_staff()
        self.affiliation.side_effect=requests.Timeout
        response=self.client.get('/buyback/staff/contracts/',secure=True)
        self.assertEqual(response.status_code,503)
        self.assertContains(response,'temporarily unavailable',status_code=503)
        user.refresh_from_db();self.assertTrue(user.is_staff)
        self.affiliation.side_effect=None
        self.assertEqual(self.client.get('/buyback/tax_edit/',secure=True).status_code,200)

    def test_manual_password_staff_session_is_not_sufficient_without_eve_proof(self):
        self.client.force_login(get_user_model().objects.create_user('old-staff',is_staff=True))
        for path in ['/buyback/tax_edit/','/buyback/staff/contracts/','/admin/']:
            self.assertEqual(self.client.get(path,secure=True).status_code,302)
        self.affiliation.assert_not_called()

    def test_one_esi_lookup_is_reused_for_staff_gate_and_pricing_on_same_request(self):
        self.authenticated_staff()
        self.client.get('/buyback/',secure=True)
        self.assertEqual(self.affiliation.call_count,1)

    def test_logout_clears_staff_identity_and_preserves_theme(self):
        self.authenticated_staff()
        response=self.client.post('/buyback/auth/eve/logout/',secure=True)
        self.assertEqual(response.status_code,302)
        self.assertNotIn('_auth_user_id',self.client.session)
        self.assertNotIn('eve_character',self.client.session)
        self.assertEqual(self.client.session['buyback_ui'],'legacy')
        self.assertEqual(self.client.get('/buyback/tax_edit/',secure=True).status_code,302)

    def test_disabled_staff_account_is_not_reactivated_by_sso(self):
        user=self.authenticated_staff();user.is_active=False;user.save(update_fields=['is_active'])
        self.client.logout()
        self.assertEqual(self.callback().status_code,403)
        user.refresh_from_db();self.assertFalse(user.is_active)

    def test_safe_return_url_and_staff_login_explain_required_character(self):
        from .staff_auth import safe_return_url
        for url in ['https://attacker.example/','//attacker.example/','/buyback/../evil','/\\attacker.example/']:
            self.assertEqual(safe_return_url(url),'/buyback/')
        self.assertEqual(safe_return_url('/buyback/tax_edit/?review=1'),'/buyback/tax_edit/?review=1')
        response=self.client.get('/buyback/auth/staff/?next=/buyback/staff/contracts/',secure=True)
        self.assertContains(response,'Spoopy Buyback')
        self.assertContains(response,'next=%2Fbuyback%2Fstaff%2Fcontracts%2F')
