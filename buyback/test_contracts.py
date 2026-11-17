from datetime import timedelta
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
import requests

from .contracts import CONTRACT_SCOPE, ContractAccessError, access_token, cipher, connect, sync_contracts
from .models import BuybackContract, ContractConnection, EveItemTax
from .test_eve_auth import METADATA

KEY = Fernet.generate_key().decode()
POLICY = dict(EVE_LOGIN_ENABLED=True,EVE_SSO_CLIENT_ID='test-client',
 EVE_SSO_CALLBACK_URL='https://buyback.spoopy.net/buyback/auth/eve/callback/',
 EVE_BUYBACK_CORPORATION_ID=98475239,EVE_TOKEN_ENCRYPTION_KEY=KEY)


@override_settings(**POLICY)
class ContractTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('contract-staff',is_staff=True)
        self.client.force_login(self.user)
        self.claims={'sub':'CHARACTER:EVE:12345','name':'Receiving Pilot','owner':'owner-hash',
            'exp':int((timezone.now()+timedelta(minutes=20)).timestamp()),'scp':[CONTRACT_SCOPE]}
        self.tokens={'access_token':'test-access-token','refresh_token':'test-refresh-token'}
        self.affiliation={'corporation_id':98475239}

    def connection(self, expired=False):
        return ContractConnection.objects.create(pk=1,connected_by=self.user,
            character_id=12345,character_name='Receiving Pilot',corporation_id=98475239,owner_hash='owner-hash',
            access_ciphertext=cipher().encrypt(b'test-access-token').decode(),
            refresh_ciphertext=cipher().encrypt(b'test-refresh-token').decode(),
            expires_at=timezone.now()+timedelta(minutes=-1 if expired else 20))

    def contract(self, ident=100, **changes):
        row={'contract_id':ident,'type':'item_exchange','assignee_id':98475239,
            'issuer_id':123,'status':'outstanding','title':'Test delivery','price':1234}
        row.update(changes)
        return row

    def response(self, rows, pages=1):
        response=Mock();response.json.return_value=rows;response.headers={'X-Pages':str(pages)}
        return response

    @patch('buyback.eve_auth.sso_metadata',return_value=METADATA)
    def test_contract_consent_only_requests_contract_scope_and_is_bound_to_staff(self, metadata):
        response=self.client.get(reverse('buyback:contracts-connect'),secure=True)
        self.assertEqual(response.status_code,302)
        query=parse_qs(urlsplit(response['Location']).query)
        self.assertEqual(query['scope'],[CONTRACT_SCOPE])
        pending=self.client.session['eve_oauth']
        self.assertEqual(pending['staff_id'],self.user.pk)
        self.assertEqual(pending['purpose'],'contracts')
        self.client.logout()
        self.assertEqual(self.client.get(reverse('buyback:contracts-connect'),secure=True).status_code,302)

    def test_all_staff_routes_reject_guests_and_nonstaff_and_mutations_require_post_csrf(self):
        self.assertEqual(self.client.get(reverse('buyback:contracts-sync'),secure=True).status_code,405)
        self.assertEqual(Client(enforce_csrf_checks=True).post(reverse('buyback:contracts-sync'),secure=True).status_code,403)
        for user in [None,get_user_model().objects.create_user('ordinary')]:
            self.client.logout()
            if user:self.client.force_login(user)
            for name in ['contracts','contracts-connect','contracts-sync','contracts-disconnect']:
                response=self.client.post(reverse('buyback:'+name),secure=True) if name.endswith(('sync','disconnect')) else self.client.get(reverse('buyback:'+name),secure=True)
                self.assertEqual(response.status_code,302)
                self.assertIn('/buyback/auth/staff/',response['Location'])

    @patch('buyback.contracts.esi_get')
    def test_connection_requires_corp_scope_and_esi_roles_then_encrypts_credentials(self,get):
        get.return_value=self.response([])
        for affiliation,claims in [({'corporation_id':98472700},self.claims),
                (self.affiliation,{**self.claims,'scp':[]})]:
            with self.assertRaises(ContractAccessError):connect(self.user,self.tokens,claims,affiliation)
        get.assert_not_called()
        get.side_effect=requests.HTTPError('denied')
        with self.assertRaises(requests.HTTPError):connect(self.user,self.tokens,self.claims,self.affiliation)
        self.assertFalse(ContractConnection.objects.exists())
        get.side_effect=None
        connection=connect(self.user,self.tokens,self.claims,self.affiliation)
        self.assertNotIn('test-access-token',connection.access_ciphertext)
        self.assertNotIn('test-refresh-token',connection.refresh_ciphertext)
        self.assertEqual(cipher().decrypt(connection.refresh_ciphertext.encode()),b'test-refresh-token')
        self.assertEqual(connection.corporation_id,98475239)

    @patch('buyback.contracts.esi_get')
    def test_paginated_sync_filters_incoming_item_exchange_and_preserves_history(self,get):
        self.connection()
        old=self.contract(1,status='finished')
        BuybackContract.objects.create(contract_id=1,corporation_id=98475239,data=old,synced_at=timezone.now())
        get.side_effect=[self.response([self.contract(),self.contract(101,assignee_id=999),self.contract(102,type='courier')],2),self.response([self.contract(103,status='finished')],2)]
        self.assertEqual(sync_contracts(),2)
        self.assertEqual(set(BuybackContract.objects.values_list('contract_id',flat=True)),{1,100,103})
        self.assertEqual(get.call_args.kwargs['page'],2)
        self.assertIsNotNone(ContractConnection.objects.get().last_synced_at)
        get.side_effect=None;get.return_value=self.response([self.contract(status='finished')])
        sync_contracts()
        self.assertEqual(BuybackContract.objects.get(pk=100).data['status'],'finished')
        self.assertEqual(BuybackContract.objects.count(),3)

    @patch('buyback.contracts.esi_get')
    def test_failed_page_never_partially_changes_snapshot(self,get):
        self.connection()
        get.side_effect=[self.response([self.contract()],2),requests.Timeout('secret-provider-details')]
        with self.assertRaises(requests.Timeout):sync_contracts()
        self.assertFalse(BuybackContract.objects.exists())
        self.assertIsNone(ContractConnection.objects.get().last_synced_at)

    @patch('buyback.eve_auth.verified_claims')
    @patch('buyback.eve_auth.sso_metadata',return_value=METADATA)
    @patch('buyback.contracts.requests.post')
    @patch('buyback.contracts.esi_get',side_effect=requests.Timeout)
    def test_rotated_token_commits_even_if_subsequent_sync_fails(self,get,post,metadata,claims):
        self.connection(expired=True)
        claims.return_value=self.claims
        post.return_value.json.return_value={'access_token':'new-access','refresh_token':'new-refresh'}
        with self.assertRaises(requests.Timeout):sync_contracts()
        connection=ContractConnection.objects.get()
        self.assertEqual(cipher().decrypt(connection.refresh_ciphertext.encode()),b'new-refresh')
        self.assertEqual(cipher().decrypt(connection.access_ciphertext.encode()),b'new-access')

    @patch('buyback.eve_auth.verified_claims')
    @patch('buyback.eve_auth.sso_metadata',return_value=METADATA)
    @patch('buyback.contracts.requests.post')
    def test_refresh_rejects_changed_character_owner_or_scopes(self,post,metadata,claims):
        self.connection(expired=True)
        post.return_value.json.return_value={'access_token':'new-access','refresh_token':'new-refresh'}
        for changes in [{'sub':'CHARACTER:EVE:999'},{'owner':'different'},{'scp':[]}]:
            claims.return_value={**self.claims,**changes}
            with self.assertRaises(ContractAccessError):access_token()
        self.assertEqual(cipher().decrypt(ContractConnection.objects.get().refresh_ciphertext.encode()),b'test-refresh-token')

    def test_dashboard_never_renders_credentials_and_disconnect_removes_them(self):
        self.connection()
        response=self.client.get(reverse('buyback:contracts'),secure=True)
        self.assertContains(response,'Receiving Pilot')
        self.assertNotContains(response,'test-access-token')
        self.assertNotContains(response,'test-refresh-token')
        self.assertNotContains(response,'access_ciphertext')
        self.assertIn('no-store',response['Cache-Control'])
        self.client.post(reverse('buyback:contracts-disconnect'),secure=True)
        self.assertFalse(ContractConnection.objects.exists())

    @patch('buyback.contracts.issuer_names',return_value={123:'Test Issuer'})
    @patch('buyback.contracts.esi_get')
    def test_item_details_are_local_queue_scoped_and_read_only(self,get,names):
        self.connection()
        row=self.contract()
        BuybackContract.objects.create(contract_id=100,corporation_id=98475239,data=row,synced_at=timezone.now())
        EveItemTax.objects.create(type_id=34,type_name='Tritanium',flat_cost=0)
        get.return_value=self.response([{'type_id':34,'quantity':100,'is_included':True}])
        response=self.client.get(reverse('buyback:contract-detail',args=[100]),secure=True)
        self.assertContains(response,'Tritanium')
        self.assertContains(response,'https://images.evetech.net/types/34/icon?size=64')
        self.assertContains(response,'Issuer Test Issuer')
        self.assertContains(response,'Offered to buyback')
        get.reset_mock()
        self.assertEqual(self.client.get(reverse('buyback:contract-detail',args=[999]),secure=True).status_code,404)
        get.assert_not_called()
        self.assertEqual(BuybackContract.objects.get().data,row)

    @patch('buyback.contracts.sync_contracts',side_effect=requests.Timeout('token=must-not-render'))
    def test_provider_errors_do_not_expose_tokens(self,sync):
        response=self.client.post(reverse('buyback:contracts-sync'),secure=True,follow=True)
        self.assertContains(response,'temporarily unavailable')
        self.assertNotContains(response,'must-not-render')

    @patch('buyback.eve_auth.sso_metadata',return_value=METADATA)
    @patch('buyback.eve_auth.requests.post')
    @patch('buyback.eve_auth.verified_claims')
    @patch('buyback.eve_auth.character_affiliation')
    @patch('buyback.contracts.esi_get')
    def test_contract_callback_stores_encrypted_connection_without_changing_member_identity(self,get,affiliation,claims,post,metadata):
        get.return_value=self.response([])
        affiliation.return_value=self.affiliation;claims.return_value=self.claims
        post.return_value.json.return_value=self.tokens
        self.client.get(reverse('buyback:contracts-connect'),secure=True)
        pending=self.client.session['eve_oauth']
        response=self.client.get(reverse('buyback:eve-callback'),{'state':pending['state'],'code':'code'},secure=True)
        self.assertRedirects(response,reverse('buyback:contracts'),fetch_redirect_response=False)
        self.assertEqual(ContractConnection.objects.get().character_id,12345)
        self.assertNotIn('eve_character',self.client.session)
        self.assertNotIn('test-refresh-token',str(dict(self.client.session)))

    @patch('buyback.eve_auth.sso_metadata',return_value=METADATA)
    @patch('buyback.eve_auth.requests.post')
    def test_contract_callback_rejects_changed_staff_session_before_exchange(self,post,metadata):
        self.client.get(reverse('buyback:contracts-connect'),secure=True)
        pending=self.client.session['eve_oauth']
        other=get_user_model().objects.create_user('other-staff',is_staff=True)
        self.client.force_login(other)
        session=self.client.session;session['eve_oauth']=pending;session.save()
        response=self.client.get(reverse('buyback:eve-callback'),{'state':pending['state'],'code':'code'},secure=True)
        self.assertEqual(response.status_code,403)
        post.assert_not_called()


    @patch('buyback.contracts.requests.post')
    def test_issuer_names_are_resolved_cached_and_show_clear_fallback(self,post):
        from django.core.cache import cache
        from .contracts import issuer_names
        cache.clear()
        post.return_value.json.return_value=[{'id':123,'name':'Firmware','category':'character'}]
        self.assertEqual(issuer_names([123,123]),{123:'Firmware'})
        self.assertEqual(post.call_args.kwargs['json'],[123])
        self.assertEqual(issuer_names([123]),{123:'Firmware'})
        self.assertEqual(post.call_count,1)
        row=self.contract()
        BuybackContract.objects.create(contract_id=100,corporation_id=98475239,data=row,synced_at=timezone.now())
        response=self.client.get(reverse('buyback:contracts'),secure=True)
        self.assertContains(response,'<th>Issuer</th>',html=True)
        self.assertContains(response,'Firmware')
        self.assertNotContains(response,'Issuer ID')
        cache.clear()
        post.side_effect=requests.Timeout
        response=self.client.get(reverse('buyback:contracts'),secure=True)
        self.assertContains(response,'Unknown issuer (123)')
