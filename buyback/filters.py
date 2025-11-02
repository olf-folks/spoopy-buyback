import requests
from django.contrib import admin
from django.utils.translation import ugettext_lazy as _
from django.contrib.admin import SimpleListFilter
from .models import EveItemTax
from spoopy.utils import get_group_name_from_api

class GroupNameFilter(SimpleListFilter):
    title = _('Group Name')
    parameter_name = 'group_name'

    def lookups(self, request, model_admin):
        groups = requests.get("https://esi.evetech.net/latest/universe/groups/").json()
        group_ids = [group['group_id'] for group in groups]
        group_names = [(str(group_id), get_group_name_from_api(group_id)) for group_id in group_ids]
        return group_names

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(group_id=int(self.value()))
        return queryset
