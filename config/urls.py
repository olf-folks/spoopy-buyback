from django.views.generic import RedirectView
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", RedirectView.as_view(url="/buyback/", permanent=False)),
    path("buyback/", include("buyback.urls", namespace="buyback")),
    
    path("admin/", admin.site.urls),
]
