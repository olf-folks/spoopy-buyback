# buyback/urls.py
from django.urls import path
from . import views


#handler404 = 'buyback.custom_404_view'  # Update with your view path
app_name = 'buyback'
urlpatterns = [
    path("", views.index, name="index"),
    path('all_item_tax/', views.all_item_tax_view, name='all_item_tax'),
    path('update_inventory/', views.update_inventory, name='update_inventory'),
    path('collapsible_tree/', views.collapsible_tree_view, name='collapsible_tree'),
    path('tax_edit/', views.category_list_view, name='category-list'),
    path('tax_edit/<int:category_id>/', views.group_list_view, name='group-list'),
    path('tax_edit/<int:category_id>/<int:group_id>/', views.item_list_view, name='item-list'),

]
