from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path('all_item_tax/', views.all_item_tax_view, name='all_item_tax'),
    path('collapsible_tree/', views.collapsible_tree_view, name='collapsible_tree'),

    
    

]
