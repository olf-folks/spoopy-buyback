from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    # path("taxdb/", views.taxdb, name="index"),
    

]
