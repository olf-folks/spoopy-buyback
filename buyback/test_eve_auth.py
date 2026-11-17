import base64
import hashlib
import time
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import jwt
import requests
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .eve_auth import verified_claims
from .models import EveItemTax

POLICY = dict(EVE_LOGIN_ENABLED=True, EVE_SSO_CLIENT_ID='test-client',
    EVE_SSO_CALLBACK_URL='https://buyback.spoopy.net/buyback/auth/eve/callback/',
    EVE_ALLIANCE_IDS=[99003214, 99010079], EVE_REQUIRE_LOGIN=False,
    EVE_SPECIAL_CORPORATION_ID=98472700)
METADATA = {'authorization_endpoint': 'https://login.eveonline.com/v2/oauth/authorize',
    'token_endpoint': 'https://login.eveonline.com/v2/oauth/token',
    'jwks_uri': 'https://login.eveonline.com/oauth/jwks'}


@override_settings(**POLICY)
class EvePricingTests(TestCase):
    def setUp(self):
        self.item = EveItemTax.objects.create(type_id=34, type_name='Tritanium',
            flat_cost=0, jita_buy_percentage=0.9)

    def character(self):
        session = self.client.session
        session['eve_character'] = {'id': 12345, 'name': 'Test Pilot'}
        session.save()

    def appraise(self):
        with patch('buyback.views.requests.post') as post:
            post.return_value.json.return_value = [{'itemType': {'eid': 34,
                'name': 'Tritanium', 'volume': 0.01},
                'immediatePrices': {'buyPrice5DayMedian': 10}}]
            return self.client.post('/buyback/', {'item_name': 'Tritanium\t100'}, secure=True)

    def test_guest_default_and_item_override_including_zero(self):
        self.assertEqual(self.appraise().context['totals_info'], [850, 1000, 85])
        self.item.outsider_jita_buy_percentage = 0.8
        self.item.save()
        self.assertEqual(self.appraise().context['totals_info'], [800, 1000, 80])
        self.item.outsider_jita_buy_percentage = 0
        self.item.save()
        self.assertEqual(self.appraise().context['totals_info'][0], 0)
        self.item.refresh_from_db()
        self.assertEqual(self.item.jita_buy_percentage, 0.9)

    @patch('buyback.eve_auth.character_affiliation')
    def test_both_alliances_members_and_outsider(self, alliance):
        self.character()
        for alliance_id, expected in [(99003214, 900), (99010079, 900), (123, 850), (None, 850)]:
            alliance.return_value = {'corporation_id': 123, 'alliance_id': alliance_id}
            self.assertAlmostEqual(self.appraise().context['totals_info'][0], expected)
        self.assertEqual(alliance.call_count, 4)

    @patch('buyback.eve_auth.character_affiliation', side_effect=requests.Timeout)
    def test_esi_failure_blocks_quote_without_using_stale_membership(self, alliance):
        self.character()
        with patch('buyback.views.requests.post') as pricing:
            response = self.client.post('/buyback/', {'item_name': 'Tritanium'}, secure=True)
        self.assertEqual(response.status_code, 503)
        pricing.assert_not_called()

    def test_staff_and_posted_membership_do_not_grant_member_price(self):
        self.client.force_login(get_user_model().objects.create_user('staff', is_staff=True))
        self.assertEqual(self.appraise().context['totals_info'][0], 850)

    def test_guest_ignores_flat_override_and_disabled_feature_preserves_percentage_pricing(self):
        self.item.flat_cost = 12
        self.item.save()
        self.assertEqual(self.appraise().context['totals_info'][0], 850)
        self.item.flat_cost = 0
        self.item.save()
        with override_settings(EVE_LOGIN_ENABLED=False):
            self.assertEqual(self.appraise().context['totals_info'][0], 900)

    @override_settings(EVE_REQUIRE_LOGIN=True)
    def test_required_login_blocks_appraisal(self):
        with patch('buyback.views.requests.post') as pricing:
            response = self.client.post('/buyback/', {'item_name': 'Tritanium'}, secure=True)
        self.assertContains(response, 'Log in')
        pricing.assert_not_called()

    def test_outsider_bulk_scope_and_item_save(self):
        staff = get_user_model().objects.create_user('editor', is_staff=True)
        self.client.force_login(staff)
        other = EveItemTax.objects.create(type_id=35, type_name='Pyerite', flat_cost=0,
            jita_buy_percentage=0.92)
        response = self.client.post('/buyback/tax_edit/?q=Tritanium',
            {'action': 'outsider_rate', 'outsider_jita_buy_percentage': '82.5'}, secure=True)
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db(); other.refresh_from_db()
        self.assertEqual(self.item.outsider_jita_buy_percentage, 0.825)
        self.assertEqual(other.outsider_jita_buy_percentage, 0.85)
        response = self.client.post(f'/buyback/tax_edit/item/{self.item.pk}/',
            {'corp_jita_buy_percentage':'85', 'jita_buy_percentage': '90', 'outsider_jita_buy_percentage': '81', 'flat_cost': '0'}, secure=True)
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.outsider_jita_buy_percentage, 0.81)
        response = self.client.post('/buyback/tax_edit/?q=Tritanium',
            {'action': 'outsider_rate', 'outsider_jita_buy_percentage': '101'}, secure=True)
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.outsider_jita_buy_percentage, 0.81)
        self.client.post('/buyback/tax_edit/?q=Tritanium',
            {'action': 'outsider_rate', 'outsider_jita_buy_percentage': ''}, secure=True)
        self.item.refresh_from_db()
        self.assertEqual(self.item.outsider_jita_buy_percentage, 0.81)
        self.assertEqual(self.item.jita_buy_percentage, 0.9)


    @patch('buyback.eve_auth.character_affiliation')
    def test_corporation_default_and_override_take_precedence_over_alliance(self, affiliation):
        self.character()
        self.item.outsider_jita_buy_percentage = 0.7
        self.item.save()
        for alliance in [99003214, 99010079, None]:
            affiliation.return_value = {'corporation_id':98472700, 'alliance_id':alliance}
            self.assertEqual(self.appraise().context['totals_info'][0], 850)
            self.assertTrue(self.appraise().context['is_corp_member'])
        self.item.corp_jita_buy_percentage = 0.97
        self.item.save()
        self.assertAlmostEqual(self.appraise().context['totals_info'][0], 970)
        self.item.corp_jita_buy_percentage = 0
        self.item.save()
        self.assertEqual(self.appraise().context['totals_info'][0], 0)
        self.item.flat_cost = 12
        self.item.save()
        self.assertEqual(self.appraise().context['totals_info'][0], 1200)

    @patch('buyback.eve_auth.character_affiliation')
    def test_corporation_change_rechecks_same_session_and_does_not_trust_browser(self, affiliation):
        self.character()
        self.item.corp_jita_buy_percentage = 0.97
        self.item.save()
        for corp, alliance, expected in [(98472700,99003214,970), (123,99003214,900), (123,None,850)]:
            affiliation.return_value = {'corporation_id':corp,'alliance_id':alliance}
            self.assertAlmostEqual(self.appraise().context['totals_info'][0], expected)
        session = self.client.session
        session['eve_character']['corporation_id'] = 98472700
        session.save()
        self.assertEqual(self.appraise().context['totals_info'][0], 850)

    def test_corp_bulk_across_pages_and_item_validation_preserve_other_rates(self):
        self.client.force_login(get_user_model().objects.create_user('corp-editor', is_staff=True))
        rows = [EveItemTax(type_id=20000+i, type_name=f'Corp item {i}',flat_cost=0,
            jita_buy_percentage=0.9,outsider_jita_buy_percentage=0.8) for i in range(105)]
        EveItemTax.objects.bulk_create(rows)
        response=self.client.post('/buyback/tax_edit/?q=Corp item',
            {'action':'corp_rate','corp_jita_buy_percentage':'95'},secure=True)
        self.assertEqual(response.status_code,302)
        self.assertEqual(EveItemTax.objects.filter(corp_jita_buy_percentage=0.95).count(),105)
        self.item.refresh_from_db()
        self.assertEqual(self.item.corp_jita_buy_percentage, 0.85)
        self.assertEqual(EveItemTax.objects.filter(outsider_jita_buy_percentage=0.8,jita_buy_percentage=0.9).count(),105)
        url=f'/buyback/tax_edit/item/{self.item.pk}/'
        self.assertContains(self.client.get(url,secure=True),'Spoopy Newbies Jita rate')
        data={'jita_buy_percentage':'90','outsider_jita_buy_percentage':'82','corp_jita_buy_percentage':'96','flat_cost':'0'}
        self.assertEqual(self.client.post(url,data,secure=True).status_code,302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.corp_jita_buy_percentage,0.96)
        data['corp_jita_buy_percentage']='101'
        self.assertEqual(self.client.post(url,data,secure=True).status_code,200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.corp_jita_buy_percentage,0.96)
        self.client.post('/buyback/tax_edit/?q=Corp item',
            {'action':'corp_rate','corp_jita_buy_percentage':''},secure=True)
        self.assertEqual(EveItemTax.objects.filter(corp_jita_buy_percentage=0.95).count(),105)


    @override_settings(EVE_CORP_PERCENTAGE=2, EVE_OUTSIDER_PERCENTAGE=3)
    @patch('buyback.eve_auth.character_affiliation')
    def test_prices_read_item_rows_and_ignore_old_environment_rates(self, affiliation):
        self.item.refresh_from_db()
        self.assertEqual(self.item.corp_jita_buy_percentage,0.85)
        self.assertEqual(self.item.outsider_jita_buy_percentage,0.85)
        self.assertFalse(EveItemTax._meta.get_field('corp_jita_buy_percentage').has_default())
        self.item.outsider_jita_buy_percentage=0.83
        self.item.corp_jita_buy_percentage=0.94
        self.item.save()
        self.assertAlmostEqual(self.appraise().context['totals_info'][0],830)
        self.character()
        affiliation.return_value={'corporation_id':98472700,'alliance_id':99003214}
        self.assertAlmostEqual(self.appraise().context['totals_info'][0],940)


    @patch('buyback.eve_auth.character_affiliation')
    def test_only_spoopy_newbies_receives_flat_price(self, affiliation):
        self.item.flat_cost=12
        self.item.save()
        self.assertAlmostEqual(self.appraise().context['totals_info'][0],850)
        self.character()
        for corp,alliance,expected,flat in [(123,99003214,900,False),
                (123,99010079,900,False),(123,None,850,False),
                (98472700,99003214,1200,True),(98472700,None,1200,True)]:
            affiliation.return_value={'corporation_id':corp,'alliance_id':alliance}
            response=self.appraise()
            self.assertAlmostEqual(response.context['totals_info'][0],expected)
            self.assertEqual(response.context['processed_items'][0]['flat_price_applied'],flat)


@override_settings(**POLICY)
class EveLoginTests(TestCase):
    @patch('buyback.eve_auth.sso_metadata', return_value=METADATA)
    def start(self, metadata):
        return self.client.get(reverse('buyback:eve-login'), secure=True)

    def test_login_uses_pkce_random_state_no_private_scopes_and_no_cache(self):
        response = self.start()
        query = parse_qs(urlsplit(response['Location']).query, keep_blank_values=True)
        pending = self.client.session['eve_oauth']
        challenge = base64.urlsafe_b64encode(hashlib.sha256(pending['verifier'].encode()).digest()).decode().rstrip('=')
        self.assertEqual(query['code_challenge'], [challenge])
        self.assertEqual(query['code_challenge_method'], ['S256'])
        self.assertEqual(query['scope'], [''])
        self.assertEqual(query['state'], [pending['state']])
        self.assertIn('no-store', response['Cache-Control'])
        self.start()
        self.assertNotEqual(self.client.session['eve_oauth']['state'], pending['state'])

    @patch('buyback.eve_auth.requests.post')
    def test_bad_state_expired_and_replay_fail_before_token_exchange(self, post):
        self.start()
        state = self.client.session['eve_oauth']['state']
        response = self.client.get(reverse('buyback:eve-callback'), {'code': 'code', 'state': 'wrong'}, secure=True)
        self.assertEqual(response.status_code, 400)
        response = self.client.get(reverse('buyback:eve-callback'), {'code': 'code', 'state': state}, secure=True)
        self.assertEqual(response.status_code, 400)
        self.start()
        response = self.client.get(reverse('buyback:eve-callback'), {'code':'code', 'state':'🚀'}, secure=True)
        self.assertEqual(response.status_code, 400)
        self.start()
        session = self.client.session
        pending = session['eve_oauth']; pending['created'] -= 601
        session['eve_oauth'] = pending; session.save()
        response = self.client.get(reverse('buyback:eve-callback'), {'code': 'code', 'state': pending['state']}, secure=True)
        self.assertEqual(response.status_code, 400)
        post.assert_not_called()

    @patch('buyback.eve_auth.character_affiliation', return_value={'corporation_id':123, 'alliance_id':99003214})
    @patch('buyback.eve_auth.verified_claims', return_value={'sub':'CHARACTER:EVE:12345', 'name':'Pilot'})
    @patch('buyback.eve_auth.requests.post')
    @patch('buyback.eve_auth.sso_metadata', return_value=METADATA)
    def test_callback_creates_eve_session_without_staff_or_retained_tokens(self, metadata, post, claims, alliance):
        post.return_value.json.return_value = {'access_token': 'access-secret', 'refresh_token':'refresh-secret'}
        self.start()
        old_key = self.client.session.session_key
        state = self.client.session['eve_oauth']['state']
        response = self.client.get(reverse('buyback:eve-callback'), {'code':'code', 'state':state}, secure=True)
        self.assertRedirects(response, '/buyback/', fetch_redirect_response=False)
        session = self.client.session
        self.assertEqual(session['eve_character'], {'id':12345,'name':'Pilot'})
        self.assertNotEqual(session.session_key, old_key)
        self.assertNotIn('_auth_user_id', session)
        self.assertNotIn('secret', str(dict(session)))
        self.assertNotIn('eve_oauth', session)
        self.assertEqual(self.client.get('/buyback/tax_edit/', secure=True).status_code, 302)

    def test_logout_requires_post_csrf_and_preserves_staff_login(self):
        self.client.force_login(get_user_model().objects.create_user('editor', is_staff=True))
        session = self.client.session
        session['eve_character'] = {'id':12345,'name':'Pilot'}; session.save()
        self.assertEqual(self.client.get(reverse('buyback:eve-logout'), secure=True).status_code, 405)
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post(reverse('buyback:eve-logout'), secure=True).status_code, 403)
        self.client.post(reverse('buyback:eve-logout'), secure=True)
        self.assertNotIn('eve_character', self.client.session)
        self.assertIn('_auth_user_id', self.client.session)

    @override_settings(EVE_LOGIN_ENABLED=False)
    def test_disabled_login_is_not_exposed(self):
        self.assertEqual(self.client.get(reverse('buyback:eve-login'), secure=True).status_code, 404)


@override_settings(**POLICY)
class EveJWTTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.jwk = __import__('json').loads(jwt.algorithms.RSAAlgorithm.to_jwk(cls.key.public_key()))
        cls.jwk.update(kid='test-key', alg='RS256')

    def token(self, **changes):
        claims = {'iss':'https://login.eveonline.com', 'aud':['test-client','EVE Online'],
            'sub':'CHARACTER:EVE:12345', 'name':'Pilot', 'iat':int(time.time()), 'exp':int(time.time())+300}
        claims.update(changes)
        return jwt.encode(claims, self.key, algorithm='RS256', headers={'kid':'test-key'})

    @patch('buyback.eve_auth.requests.get')
    def test_signature_audience_issuer_expiry_subject_and_algorithm_validation(self, get):
        get.return_value.json.return_value = {'keys':[self.jwk]}
        self.assertEqual(verified_claims(self.token(), METADATA)['sub'], 'CHARACTER:EVE:12345')
        for changes in [{'aud':['wrong-client','EVE Online']}, {'aud':['test-client']},
            {'iss':'https://attacker.example'}, {'exp':int(time.time())-10}, {'sub':'wrong'}]:
            with self.assertRaises((ValueError, jwt.PyJWTError)):
                verified_claims(self.token(**changes), METADATA)
        with self.assertRaises((ValueError, jwt.PyJWTError)):
            verified_claims(jwt.encode({'sub':'CHARACTER:EVE:12345'}, 'a'*32, algorithm='HS256'), METADATA)
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with self.assertRaises(jwt.PyJWTError):
            verified_claims(jwt.encode({'exp':int(time.time())+300}, other, algorithm='RS256',headers={'kid':'test-key'}), METADATA)


class EveAffiliationTests(TestCase):
    @patch('buyback.eve_auth.requests.post')
    def test_affiliation_matches_verified_character_and_handles_no_alliance(self, post):
        from .eve_auth import character_alliance
        post.return_value.json.return_value = [{'character_id': 12345, 'corporation_id':123, 'alliance_id':99003214}]
        self.assertEqual(character_alliance(12345), 99003214)
        self.assertEqual(post.call_args.kwargs['json'], [12345])
        post.return_value.json.return_value = [{'character_id':12345, 'corporation_id':123}]
        self.assertIsNone(character_alliance(12345))
        post.return_value.json.return_value = [{'character_id':99999, 'alliance_id':99003214}]
        with self.assertRaises(StopIteration):
            character_alliance(12345)
