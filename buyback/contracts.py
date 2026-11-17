"""Read-only corporation contract integration. No contract or wallet writes."""
from datetime import datetime, timedelta, timezone as dt_timezone
import uuid

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib import messages
from .staff_auth import staff_member_required
from django.core.paginator import Paginator
from django.core.cache import cache
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
import requests

from .models import BuybackContract, ContractConnection, EveItemTax

CONTRACT_SCOPE = 'esi-contracts.read_corporation_contracts.v1'
ESI = 'https://esi.evetech.net'
HEADERS = {'User-Agent': 'SpoopyBuyback/1.0 (https://buyback.spoopy.net)',
           'X-Compatibility-Date': '2026-11-14'}


class ContractAccessError(Exception):
    pass


def cipher():
    key = getattr(settings, 'EVE_TOKEN_ENCRYPTION_KEY', '')
    if not key:
        raise ContractAccessError('Contract authorization is not configured on the server.')
    return Fernet(key.encode())


def esi_get(path, token, **params):
    response = requests.get(ESI + path, headers={**HEADERS, 'Authorization': 'Bearer ' + token},
                            params=params, timeout=20)
    response.raise_for_status()
    return response


def connect(user, tokens, claims, affiliation):
    if not user.is_active or not user.is_staff:
        raise ContractAccessError('Staff login is required.')
    if CONTRACT_SCOPE not in claims.get('scp', []):
        raise ContractAccessError('Corporation contract access was not granted.')
    corp_id = settings.EVE_BUYBACK_CORPORATION_ID
    if affiliation['corporation_id'] != corp_id:
        raise ContractAccessError('Select a character in Spoopy Buyback with access to corporation contracts.')
    if not tokens.get('refresh_token'):
        raise ContractAccessError('EVE did not provide the authorization needed for syncing.')
    encryption = cipher()
    # ESI verifies the character's required corporation roles before anything is stored.
    probe = esi_get(f'/corporations/{corp_id}/contracts', tokens['access_token'], page=1)
    if not isinstance(probe.json(), list):
        raise ContractAccessError('Unexpected corporation contracts response.')
    connection, _ = ContractConnection.objects.update_or_create(pk=1, defaults={
        'authorization_id': uuid.uuid4(), 'connected_by': user,
        'character_id': int(claims['sub'].rsplit(':', 1)[1]), 'character_name': claims['name'],
        'corporation_id': corp_id, 'owner_hash': claims.get('owner', ''),
        'access_ciphertext': encryption.encrypt(tokens['access_token'].encode()).decode(),
        'refresh_ciphertext': encryption.encrypt(tokens['refresh_token'].encode()).decode(),
        'expires_at': datetime.fromtimestamp(claims['exp'], tz=dt_timezone.utc), 'last_synced_at': None,
    })
    return connection


def access_token():
    # Keep refresh rotation serialized and commit it before subsequent ESI calls:
    # an ESI outage must not roll back a successfully rotated refresh token.
    with transaction.atomic():
        connection = ContractConnection.objects.select_for_update().get(pk=1)
        encryption = cipher()
        if connection.corporation_id != settings.EVE_BUYBACK_CORPORATION_ID:
            raise ContractAccessError('Reconnect the receiving corporation.')
        if connection.expires_at > timezone.now() + timedelta(seconds=60):
            return connection, encryption.decrypt(connection.access_ciphertext.encode()).decode()
        from .eve_auth import sso_metadata, verified_claims
        metadata = sso_metadata()
        response = requests.post(metadata['token_endpoint'], data={
            'grant_type': 'refresh_token', 'client_id': settings.EVE_SSO_CLIENT_ID,
            'refresh_token': encryption.decrypt(connection.refresh_ciphertext.encode()).decode(),
        }, timeout=20)
        response.raise_for_status()
        tokens = response.json()
        claims = verified_claims(tokens['access_token'], metadata)
        if (claims['sub'] != f'CHARACTER:EVE:{connection.character_id}'
                or CONTRACT_SCOPE not in claims.get('scp', [])
                or (connection.owner_hash and claims.get('owner') != connection.owner_hash)):
            raise ContractAccessError('The EVE authorization changed. Please reconnect.')
        connection.access_ciphertext = encryption.encrypt(tokens['access_token'].encode()).decode()
        if tokens.get('refresh_token'):
            connection.refresh_ciphertext = encryption.encrypt(tokens['refresh_token'].encode()).decode()
        connection.expires_at = datetime.fromtimestamp(claims['exp'], tz=dt_timezone.utc)
        connection.save(update_fields=['access_ciphertext', 'refresh_ciphertext', 'expires_at'])
        return connection, tokens['access_token']


def sync_contracts():
    connection, token = access_token()
    incoming = []
    page, pages = 1, 1
    while page <= pages:
        response = esi_get(f'/corporations/{connection.corporation_id}/contracts', token, page=page)
        pages = int(response.headers.get('X-Pages', '1'))
        if pages < 1 or pages > 100:
            raise ContractAccessError('Unexpected number of contract pages; no snapshot was changed.')
        rows = response.json()
        if not isinstance(rows, list):
            raise ContractAccessError('Unexpected contracts response.')
        for row in rows:
            if row['type'] == 'item_exchange' and row['assignee_id'] == connection.corporation_id:
                if not isinstance(row['contract_id'], int) or row['contract_id'] <= 0:
                    raise ContractAccessError('Invalid contract ID.')
                incoming.append(row)
        page += 1
    synced = timezone.now()
    with transaction.atomic():
        current = ContractConnection.objects.select_for_update().get(pk=1)
        if current.authorization_id != connection.authorization_id:
            raise ContractAccessError('Authorization changed during sync. Retry with the new connection.')
        for row in incoming:
            BuybackContract.objects.update_or_create(contract_id=row['contract_id'], defaults={
                'corporation_id': current.corporation_id, 'data': row, 'synced_at': synced})
        current.last_synced_at = synced
        current.save(update_fields=['last_synced_at'])
    return len(incoming)


def issuer_names(ids):
    ids = {ident for ident in ids if isinstance(ident, int) and ident > 0}
    keys = {ident: f'eve-issuer-name:{ident}' for ident in ids}
    cached = cache.get_many(keys.values())
    names = {ident: cached[key] for ident, key in keys.items() if key in cached}
    missing = ids - names.keys()
    if missing:
        try:
            response = requests.post(ESI + '/universe/names', json=sorted(missing),
                                     headers=HEADERS, timeout=10)
            response.raise_for_status()
            resolved = {row['id']: row['name'] for row in response.json()
                        if row['id'] in missing and isinstance(row['name'], str) and row['name']}
            cache.set_many({keys[ident]: name for ident, name in resolved.items()}, 86400)
            names.update(resolved)
        except (requests.RequestException, KeyError, TypeError, ValueError):
            pass
    return names


def safe_error(exc):
    if isinstance(exc, ContractAccessError):
        return str(exc)
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        if exc.response.status_code in (401, 403):
            return 'EVE denied access. Reconnect a Spoopy Buyback character with the required corporation roles.'
        if exc.response.status_code in (420, 429):
            return 'ESI is rate limiting requests. Retry later.'
    return 'Contract sync is temporarily unavailable. Retry later or reconnect the EVE character.'


@never_cache
@staff_member_required
@require_GET
def contract_queue(request):
    connection = ContractConnection.objects.filter(pk=1).first()
    contracts = BuybackContract.objects.filter(corporation_id=settings.EVE_BUYBACK_CORPORATION_ID)
    status = request.GET.get('status', '')
    if status in ('outstanding', 'in_progress', 'finished', 'cancelled', 'rejected', 'failed', 'deleted', 'reversed'):
        contracts = contracts.filter(data__status=status)
    page = Paginator(contracts, 50).get_page(request.GET.get('page'))
    names = issuer_names([contract.data.get('issuer_id') for contract in page])
    for contract in page:
        ident = contract.data.get('issuer_id')
        contract.issuer_name = names.get(ident, f'Unknown issuer ({ident})')
    return render(request, 'buyback/contracts.html', {'connection': connection,
        'page_obj': page, 'status': status, 'contracts_page': True})


@never_cache
@staff_member_required
@require_GET
def contract_connect(request):
    from .eve_auth import eve_login
    return eve_login(request, purpose='contracts')


@never_cache
@staff_member_required
@require_POST
def contract_disconnect(request):
    ContractConnection.objects.filter(pk=1).delete()
    messages.success(request, 'Contract authorization removed. Saved contract history is retained.')
    return redirect('buyback:contracts')


@never_cache
@staff_member_required
@require_POST
def contract_sync(request):
    try:
        count = sync_contracts()
        messages.success(request, f'Synced {count} incoming item-exchange contracts.')
    except Exception as exc:
        # Never include provider payloads or credentials in browser errors.
        messages.error(request, safe_error(exc))
    return redirect('buyback:contracts')


@never_cache
@staff_member_required
@require_GET
def contract_detail(request, contract_id):
    contract = get_object_or_404(BuybackContract, pk=contract_id,
                                corporation_id=settings.EVE_BUYBACK_CORPORATION_ID)
    ident = contract.data.get('issuer_id')
    contract.issuer_name = issuer_names([ident]).get(ident, f'Unknown issuer ({ident})')
    items, error = [], ''
    try:
        connection, token = access_token()
        items = esi_get(f'/corporations/{connection.corporation_id}/contracts/{contract_id}/items', token).json()
        if not isinstance(items, list):
            raise ContractAccessError('Unexpected contract items response.')
        names = dict(EveItemTax.objects.filter(type_id__in=[row['type_id'] for row in items]).values_list('type_id', 'type_name'))
        for item in items:
            item['name'] = names.get(item['type_id'], f"Type {item['type_id']}")
    except Exception as exc:
        items, error = [], safe_error(exc)
    return render(request, 'buyback/contract_detail.html', {
        'contract': contract, 'items': items, 'error': error, 'contracts_page': True})
