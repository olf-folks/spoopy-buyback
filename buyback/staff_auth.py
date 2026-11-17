"""Staff eligibility is proven by the selected EVE character's current corporation."""
from functools import wraps
from urllib.parse import urlencode, urlsplit
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.models import Permission
from django.contrib.auth.views import redirect_to_login
from django.db import IntegrityError, transaction
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
import requests

from .models import EveStaffIdentity


def staff_auth_enabled():
    return getattr(settings, 'EVE_STAFF_AUTH_ENABLED', True)


def safe_return_url(value):
    try:
        parsed = urlsplit(value)
        if (not parsed.scheme and not parsed.netloc and '\\' not in value
                and (parsed.path == '/buyback/' or parsed.path.startswith(
                    ('/buyback/tax_edit/', '/buyback/staff/', '/admin/')))):
            return value
    except (ValueError, TypeError):
        pass
    return reverse('buyback:index')


def staff_member_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.user.is_active and request.user.is_staff:
            return view(request, *args, **kwargs)
        return redirect_to_login(request.get_full_path(), reverse('buyback:staff-login'))
    return wrapped


@never_cache
@require_GET
def staff_login(request):
    target = safe_return_url(request.GET.get('next', '/buyback/tax_edit/'))
    if request.user.is_active and request.user.is_staff:
        return redirect(target)
    return render(request, 'buyback/staff_login.html', {
        'eve_signin_url': reverse('buyback:eve-login') + '?' + urlencode({'next': target})})


def establish_identity(request, claims, affiliation):
    """Grant basic staff permissions to verified receiving-corporation members only."""
    character_id = int(claims['sub'].rsplit(':', 1)[1])
    ui = request.session.get('buyback_ui')
    eligible = affiliation['corporation_id'] == settings.EVE_BUYBACK_CORPORATION_ID
    if eligible:
        for attempt in range(2):
            try:
                with transaction.atomic():
                    identity = EveStaffIdentity.objects.select_for_update().filter(pk=character_id).first()
                    if identity is None:
                        user = get_user_model().objects.create_user(
                            username=f'eve_{character_id}_{uuid.uuid4().hex[:8]}', password=None,
                            is_staff=True, is_superuser=False)
                        identity = EveStaffIdentity.objects.create(character_id=character_id,
                            user=user, character_name=claims['name'])
                    else:
                        user = identity.user
                        if not user.is_active:
                            return HttpResponseForbidden('This staff account is disabled.')
                        user.is_staff = True
                        user.is_superuser = False
                        user.save(update_fields=['is_staff', 'is_superuser'])
                        identity.character_name = claims['name']
                        identity.save(update_fields=['character_name'])
                    permissions = Permission.objects.filter(content_type__app_label='buyback',
                        content_type__model='eveitemtax', codename__in=['view_eveitemtax','change_eveitemtax'])
                    user.user_permissions.add(*permissions)
                break
            except IntegrityError:
                if attempt:
                    raise
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    elif request.user.is_authenticated:
        logout(request)
    if ui in ('legacy', 'modern'):
        request.session['buyback_ui'] = ui
    request.session['eve_character'] = {'id': character_id, 'name': claims['name']}
    return None


class EveStaffMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if staff_auth_enabled() and request.user.is_authenticated:
            user = request.user
            identity = EveStaffIdentity.objects.filter(user_id=user.pk).first()
            if user.is_staff or identity:
                character = request.session.get('eve_character') or {}
                user.is_staff = False
                verified = False
                try:
                    if (user.is_active and character.get('id')
                            and (identity is None or identity.character_id == character['id'])):
                        from .eve_auth import request_affiliation
                        affiliation = request_affiliation(request, character['id'])
                        user.is_staff = affiliation['corporation_id'] == settings.EVE_BUYBACK_CORPORATION_ID
                        verified = True
                except (requests.RequestException, ValueError, KeyError, TypeError, StopIteration):
                    if request.path.startswith(('/buyback/tax_edit/', '/buyback/staff/', '/admin/')):
                        return render(request, 'buyback/staff_login.html',
                            {'staff_verification_unavailable': True}, status=503)
                if identity and verified:
                    get_user_model().objects.filter(pk=user.pk).update(is_staff=user.is_staff)
        return self.get_response(request)
