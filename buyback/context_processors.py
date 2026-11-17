from django.conf import settings


def ui_preference(request):
    selection = request.GET.get('ui')
    if selection in ('legacy', 'modern'):
        request.session['buyback_ui'] = selection
    return request.session.get('buyback_ui') == 'legacy'


def site_navigation(request):
    character = request.session.get('eve_character') or {}
    legacy_ui = ui_preference(request)
    query = request.GET.copy()
    query['ui'] = 'modern' if legacy_ui else 'legacy'
    return {
        'nav_eve_enabled': getattr(settings, 'EVE_LOGIN_ENABLED', False),
        'nav_eve_name': character.get('name', ''),
        'legacy_ui': legacy_ui,
        'show_ui_toggle': not request.path.startswith('/buyback/auth/'),
        'ui_switch_url': request.path + '?' + query.urlencode(),
    }
