# buyback/urls.py
from django.urls import path
from . import views, eve_auth, contracts, staff_auth
from .tax_editor import market_tax_editor


#handler404 = 'buyback.custom_404_view'  # Update with your view path
app_name = 'buyback'
urlpatterns = [
    path('auth/staff/', staff_auth.staff_login, name='staff-login'),
    path('staff/contracts/', contracts.contract_queue, name='contracts'),
    path('staff/contracts/connect/', contracts.contract_connect, name='contracts-connect'),
    path('staff/contracts/disconnect/', contracts.contract_disconnect, name='contracts-disconnect'),
    path('staff/contracts/sync/', contracts.contract_sync, name='contracts-sync'),
    path('staff/contracts/<int:contract_id>/', contracts.contract_detail, name='contract-detail'),
    path('auth/eve/login/', eve_auth.eve_login, name='eve-login'),
    path('auth/eve/callback/', eve_auth.eve_callback, name='eve-callback'),
    path('auth/eve/logout/', eve_auth.eve_logout, name='eve-logout'),
    path("", views.index, name="index"),
    path('all_item_tax/', views.all_item_tax_view, name='all_item_tax'),
    path('update_inventory/', views.update_inventory, name='update_inventory'),
    path('collapsible_tree/', views.collapsible_tree_view, name='collapsible_tree'),
    path('tax_edit/item/<int:item_id>/', market_tax_editor, name='item-tax-editor'),
    path('tax_edit/market/<int:market_group_id>/', market_tax_editor, name='market-tax-editor'),
    path('tax_edit/', views.category_list_view, name='category-list'),
    path('tax_edit/<int:category_id>/', views.group_list_view, name='group-list'),
    path('tax_edit/<int:category_id>/<int:group_id>/', views.item_list_view, name='item-list'),

]
