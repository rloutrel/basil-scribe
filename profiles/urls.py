from django.urls import path

from . import views

app_name = "profiles"

urlpatterns = [
    path("select-profile/", views.select_profile, name="select"),
]
