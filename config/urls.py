from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("buyback/", include("buyback.urls", namespace="buyback")),
    
    path("admin/", admin.site.urls),
]
