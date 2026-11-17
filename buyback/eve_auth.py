"""Scope-free EVE identity login, separate from Django staff authentication."""
import base64
import hashlib
import re
import secrets
import time
from urllib.parse import urlencode, urlsplit

import jwt
import requests
from django.conf import settings
from django.core.cache import cache
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

METADATA_URL = 'https://login.eveonline.com/.well-known/oauth-authorization-server'


def enabled():
    return getattr(settings, 'EVE_LOGIN_ENABLED', False)


def sso_metadata():
    metadata = cache.get('eve-sso-metadata')
    if metadata is None:
        response = requests.get(METADATA_URL, timeout=10)
        response.raise_for_status()
        metadata = response.json()
        for name in ('authorization_endpoint', 'token_endpoint', 'jwks_uri'):
            parsed = urlsplit(metadata[name])
            if parsed.scheme != 'https' or parsed.netloc != 'login.eveonline.com':
                raise ValueError('Unexpected SSO endpoint')
        cache.set('eve-sso-metadata', metadata, 300)
    return metadata


def verified_claims(token, metadata):
    header = jwt.get_unverified_header(token)
    if header.get('alg') != 'RS256':
        raise ValueError('Unexpected signing algorithm')
    # Fetch current keys so key rotation does not invalidate a valid login.
    response = requests.get(metadata['jwks_uri'], timeout=10)
    response.raise_for_status()
    key = next(key for key in response.json()['keys'] if key['kid'] == header.get('kid'))
    claims = jwt.decode(token, jwt.PyJWK.from_dict(key).key, algorithms=['RS256'],
        audience=settings.EVE_SSO_CLIENT_ID,
        issuer=['https://login.eveonline.com', 'https://login.eveonline.com/', 'login.eveonline.com'],
        options={'require': ['exp', 'iat', 'iss', 'aud', 'sub']})
    if 'EVE Online' not in claims['aud'] or not re.fullmatch(r'CHARACTER:EVE:[1-9][0-9]*', claims['sub']):
        raise ValueError('Invalid character token')
    return claims


def character_affiliation(character_id):
    response = requests.post('https://esi.evetech.net/latest/characters/affiliation/',
        json=[character_id], headers={'User-Agent': 'SpoopyBuyback/1.0 (https://buyback.spoopy.net)'},
        timeout=10)
    response.raise_for_status()
    row = next(row for row in response.json() if row['character_id'] == character_id)
    # Missing corporation data cannot safely establish the pricing tier.
    if not isinstance(row.get('corporation_id'), int) or row['corporation_id'] <= 0:
        raise ValueError('Invalid character affiliation')
    return row


def character_alliance(character_id):
    return character_affiliation(character_id).get('alliance_id')


def request_affiliation(request, character_id):
    cached = getattr(request, '_eve_affiliation_cache', {})
    if character_id not in cached:
        try:
            cached[character_id] = character_affiliation(character_id)
        except (requests.RequestException, ValueError, KeyError, TypeError, StopIteration) as exc:
            cached[character_id] = exc
        request._eve_affiliation_cache = cached
    value = cached[character_id]
    if isinstance(value, Exception):
        raise value
    return value


def pricing_identity(request):
    identity = {'enabled': enabled(), 'is_corp_member': False, 'is_member': False, 'character_name': '',
        'login_required': False, 'unavailable': False}
    if not identity['enabled']:
        return identity
    character = request.session.get('eve_character')
    identity['login_required'] = getattr(settings, 'EVE_REQUIRE_LOGIN', False) and not character
    if character:
        identity['character_name'] = character['name']
        try:
            # Recheck on each appraisal; membership is never accepted from browser input.
            affiliation = request_affiliation(request, character['id'])
            identity['is_corp_member'] = affiliation['corporation_id'] == settings.EVE_SPECIAL_CORPORATION_ID
            identity['is_member'] = affiliation.get('alliance_id') in settings.EVE_ALLIANCE_IDS
        except (requests.RequestException, ValueError, KeyError, TypeError, StopIteration):
            # Do not silently quote the wrong rate during an ESI outage.
            identity['unavailable'] = True
    return identity


@never_cache
@require_GET
def eve_login(request, purpose='identity'):
    if not enabled():
        raise Http404
    try:
        if purpose == 'contracts':
            from .contracts import CONTRACT_SCOPE, cipher
            if not request.user.is_authenticated or not request.user.is_active or not request.user.is_staff:
                raise Http404
            try:
                cipher()
            except Exception:
                return render(request, 'buyback/eve_login.html', {'unavailable': True}, status=503)
            scopes = CONTRACT_SCOPE
        else:
            scopes = ''
        metadata = sso_metadata()
        if not settings.EVE_SSO_CLIENT_ID:
            raise ValueError('Missing client ID')
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        request.session['eve_oauth'] = {'state': state, 'verifier': verifier, 'created': time.time(),
            'purpose': purpose, 'staff_id': request.user.pk if purpose == 'contracts' else None}
        from .staff_auth import safe_return_url
        request.session['eve_oauth']['return_url'] = safe_return_url(request.GET.get('next', '/buyback/'))
        return redirect(metadata['authorization_endpoint'] + '?' + urlencode({
            'response_type': 'code', 'client_id': settings.EVE_SSO_CLIENT_ID,
            'redirect_uri': settings.EVE_SSO_CALLBACK_URL, 'scope': scopes, 'state': state,
            'code_challenge': challenge, 'code_challenge_method': 'S256'}))
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return render(request, 'buyback/eve_login.html', {'unavailable': True}, status=503)


@never_cache
@require_GET
def eve_callback(request):
    if not enabled():
        raise Http404
    pending = request.session.pop('eve_oauth', None)
    if (not pending or not secrets.compare_digest(request.GET.get('state', '').encode(), pending['state'].encode())
            or time.time() - pending['created'] > 600 or not request.GET.get('code')):
        return render(request, 'buyback/eve_login.html', {'login_error': True}, status=400)
    if pending.get('purpose') == 'contracts' and (
            not request.user.is_authenticated or not request.user.is_active or not request.user.is_staff
            or pending.get('staff_id') != request.user.pk):
        return render(request, 'buyback/eve_login.html', {'login_error': True}, status=403)
    try:
        metadata = sso_metadata()
        response = requests.post(metadata['token_endpoint'], data={
            'grant_type': 'authorization_code', 'code': request.GET['code'],
            'client_id': settings.EVE_SSO_CLIENT_ID, 'code_verifier': pending['verifier'],
            'redirect_uri': settings.EVE_SSO_CALLBACK_URL}, timeout=10)
        response.raise_for_status()
        tokens = response.json()
        claims = verified_claims(tokens['access_token'], metadata)
        character_id = int(claims['sub'].rsplit(':', 1)[1])
        # Verify affiliation before completing either kind of authorization.
        affiliation = character_affiliation(character_id)
        if pending.get('purpose') == 'contracts':
            from .contracts import connect, safe_error
            from django.contrib import messages
            try:
                connect(request.user, tokens, claims, affiliation)
                messages.success(request, 'Connected EVE corporation contracts. Use Refresh contracts to load the queue.')
            except Exception as exc:
                messages.error(request, safe_error(exc))
            return redirect('buyback:contracts')
        from .staff_auth import establish_identity, staff_auth_enabled
        if staff_auth_enabled():
            denied = establish_identity(request, claims, affiliation)
            if denied is not None:
                return denied
        else:
            request.session.cycle_key()
            request.session['eve_character'] = {'id': character_id, 'name': claims['name']}
        return redirect(pending.get('return_url', reverse('buyback:index')))
    except (requests.RequestException, jwt.PyJWTError, ValueError, KeyError, TypeError, StopIteration):
        return render(request, 'buyback/eve_login.html', {'login_error': True}, status=400)


@never_cache
@require_POST
def eve_logout(request):
    from .staff_auth import staff_auth_enabled
    if staff_auth_enabled():
        from django.contrib.auth import logout
        ui = request.session.get('buyback_ui')
        logout(request)
        if ui in ('legacy', 'modern'):
            request.session['buyback_ui'] = ui
    request.session.pop('eve_character', None)
    request.session.pop('eve_oauth', None)
    request.session.cycle_key()
    return redirect(reverse('buyback:index'))
