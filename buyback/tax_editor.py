from decimal import Decimal
from urllib.parse import urlencode, urlsplit

from django.contrib import messages
from .staff_auth import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Count, Max, Min, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import CorpRateForm, OutsiderRateForm, FlatCostForm, ItemTaxForm, JitaBuyPercentageForm, ReviewStatusForm
from .models import EveItemTax, MarketGroup, MarketType


@staff_member_required
def market_tax_editor(request, market_group_id=None, item_id=None):
    editing_item = get_object_or_404(EveItemTax, pk=item_id) if item_id is not None else None
    if editing_item:
        market_group_id = MarketType.objects.filter(type_id=editing_item.type_id).values_list(
            'market_group_id', flat=True).first()
    review_only = request.GET.get('review') == '1'
    groups = list(MarketGroup.objects.all())
    nodes = {group.pk: {'id': group.pk, 'name': group.name,
        'parent_id': group.parent_id, 'children': [], 'count': 0, 'review_count': 0,
        'url': reverse('buyback:market-tax-editor', args=[group.pk]) + ('?review=1' if review_only else '')}
        for group in groups}
    roots = []
    for node in nodes.values():
        parent = nodes.get(node['parent_id'])
        (parent['children'] if parent else roots).append(node)
    selected = nodes.get(market_group_id)
    if market_group_id is not None and selected is None:
        raise Http404('Market group not found')
    counts = MarketType.objects.filter(type_id__in=EveItemTax.objects.values('type_id')).values(
        'market_group_id').annotate(total=Count('type_id'), review_total=Count('type_id',
            filter=Q(type_id__in=EveItemTax.objects.filter(needs_review=True).values('type_id'))))
    for row in counts:
        nodes[row['market_group_id']]['count'] = row['total']
        nodes[row['market_group_id']]['review_count'] = row['review_total']
    ancestors = []
    current = selected
    while current:
        ancestors.append(current)
        current = nodes.get(current['parent_id'])
    opened = {node['id'] for node in ancestors}

    def populate(node):
        for child in node['children']:
            populate(child)
            node['count'] += child['count']
            node['review_count'] += child['review_count']
        node['children'] = [child for child in node['children'] if child['count']]
        node['open'] = node['id'] in opened
        node['selected'] = node['id'] == market_group_id
    for root in roots:
        populate(root)
    roots = [root for root in roots if root['count']]
    items = EveItemTax.objects.all()
    unlisted = market_group_id is None and request.GET.get('unlisted') == '1'
    unlisted_items = items.exclude(type_id__in=MarketType.objects.values('type_id'))
    unlisted_count = unlisted_items.count()
    unlisted_review_count = unlisted_items.filter(needs_review=True).count()
    all_review_count = items.filter(needs_review=True).count()
    if selected:
        descendants = set()
        pending = [selected]
        while pending:
            node = pending.pop()
            descendants.add(node['id'])
            pending.extend(node['children'])
        items = items.filter(type_id__in=MarketType.objects.filter(
            market_group_id__in=descendants).values('type_id'))
    elif unlisted:
        items = items.exclude(type_id__in=MarketType.objects.values('type_id'))
    search = request.GET.get('q', '').strip()[:100]
    if search:
        query = Q(type_name__icontains=search)
        if search.isdigit():
            query |= Q(type_id=int(search))
        items = items.filter(query)
    if review_only:
        items = items.filter(needs_review=True)
    total = items.count()
    rate_range = items.aggregate(low=Min('jita_buy_percentage'), high=Max('jita_buy_percentage'),
        pending_review=Count('pk', filter=Q(needs_review=True)))
    initial_rate = round(rate_range['low'] * 100, 6) if rate_range['low'] is not None and rate_range['low'] == rate_range['high'] else None
    rate_form = JitaBuyPercentageForm(initial={'jita_buy_percentage': initial_rate})
    flat_form = FlatCostForm()
    initial_review = ''
    if total:
        if rate_range['pending_review'] == total:
            initial_review = 'true'
        elif rate_range['pending_review'] == 0:
            initial_review = 'false'
    review_form = ReviewStatusForm(initial={'needs_review': initial_review})
    outsider_form = OutsiderRateForm()
    corp_form = CorpRateForm()
    if editing_item:
        return_url = request.GET.get('next', '')
        try:
            parsed = urlsplit(return_url)
        except ValueError:
            return_url = ''
            parsed = urlsplit('')
        allowed_paths = {reverse('buyback:category-list')} | {urlsplit(node['url']).path for node in nodes.values()}
        if parsed.scheme or parsed.netloc or parsed.path not in allowed_paths or '\\' in return_url:
            return_url = selected['url'] if selected else reverse('buyback:category-list')
        item_form = ItemTaxForm(request.POST if request.method == 'POST' else None, initial={
            'jita_buy_percentage': round(editing_item.jita_buy_percentage * 100, 6),
            'outsider_jita_buy_percentage': round(editing_item.outsider_jita_buy_percentage * 100, 6),
            'corp_jita_buy_percentage': round(editing_item.corp_jita_buy_percentage * 100, 6),
            'flat_cost': editing_item.flat_cost, 'hauling_fee': editing_item.hauling_fee,
            'needs_review': editing_item.needs_review,
        })
        if request.method == 'POST' and item_form.is_valid():
            values = item_form.cleaned_data
            EveItemTax.objects.filter(pk=editing_item.pk).update(
                jita_buy_percentage=float(values['jita_buy_percentage'] / Decimal(100)),
                outsider_jita_buy_percentage=float(values['outsider_jita_buy_percentage'] / Decimal(100)),
                corp_jita_buy_percentage=float(values['corp_jita_buy_percentage'] / Decimal(100)),
                flat_cost=values['flat_cost'], hauling_fee=values['hauling_fee'],
                needs_review=values['needs_review'])
            messages.success(request, f'Updated {editing_item.type_name}.')
            return redirect(return_url)
        return render(request, 'buyback/item_tax_edit.html', {
            'market_tree': roots, 'selected': selected, 'breadcrumbs': list(reversed(ancestors)),
            'unlisted_count': unlisted_count, 'unlisted_review_count': unlisted_review_count,
            'all_review_count': all_review_count, 'review_only': review_only, 'editing_item': editing_item,
            'item_form': item_form, 'return_url': return_url,
        })
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'rate':
            rate_form = JitaBuyPercentageForm(request.POST)
            if rate_form.is_valid():
                rate = rate_form.cleaned_data['jita_buy_percentage']
                changed = items.update(jita_buy_percentage=float(rate / Decimal(100)))
                messages.success(request, f'Set Jita buy rate to {rate}% for {changed:,} items.')
                return redirect(request.get_full_path())
        elif action == 'corp_rate':
            corp_form = CorpRateForm(request.POST)
            if corp_form.is_valid():
                rate = corp_form.cleaned_data['corp_jita_buy_percentage']
                changed = items.update(corp_jita_buy_percentage=float(rate / Decimal(100)))
                messages.success(request, f'Updated Spoopy Newbies Jita rate for {changed:,} items.')
                return redirect(request.get_full_path())
        elif action == 'outsider_rate':
            outsider_form = OutsiderRateForm(request.POST)
            if outsider_form.is_valid():
                rate = outsider_form.cleaned_data['outsider_jita_buy_percentage']
                changed = items.update(outsider_jita_buy_percentage=float(rate / Decimal(100)))
                messages.success(request, f'Updated outsider Jita rate for {changed:,} items.')
                return redirect(request.get_full_path())
        elif action == 'flat':
            flat_form = FlatCostForm(request.POST)
            if flat_form.is_valid():
                changed = items.update(flat_cost=flat_form.cleaned_data['flat_cost'])
                messages.success(request, f'Updated flat price for {changed:,} items.')
                return redirect(request.get_full_path())
        elif action == 'review':
            review_form = ReviewStatusForm(request.POST)
            if review_form.is_valid():
                changed = items.update(needs_review=review_form.cleaned_data['needs_review'])
                messages.success(request, f'Updated review status for {changed:,} items.')
                return redirect(request.get_full_path())
        else:
            messages.error(request, 'Choose a rate, flat-price or review action.')
    page = Paginator(items.order_by('type_name', 'taxid'), 100).get_page(request.GET.get('page'))
    for item in page:
        item.display_rate = item.jita_buy_percentage * 100
        item.corp_display_rate = item.corp_jita_buy_percentage * 100
        item.outsider_display_rate = item.outsider_jita_buy_percentage * 100
    params = {}
    if search:
        params['q'] = search
    if unlisted:
        params['unlisted'] = '1'
    if review_only:
        params['review'] = '1'
    page_query = urlencode(params)
    return render(request, 'buyback/tax_edit.html', {
        'market_tree': roots, 'selected': selected, 'breadcrumbs': list(reversed(ancestors)),
        'unlisted': unlisted, 'unlisted_count': unlisted_count, 'unlisted_review_count': unlisted_review_count,
            'all_review_count': all_review_count, 'review_only': review_only,
        'scope_title': selected['name'] if selected else ('Outside the market' if unlisted else 'All items'),
        'search': search, 'total': total, 'page_obj': page, 'rate_form': rate_form,
        'corp_form': corp_form, 'outsider_form': outsider_form, 'flat_form': flat_form, 'review_form': review_form, 'page_query': page_query,
        'all_selected': market_group_id is None and not unlisted,
    })
