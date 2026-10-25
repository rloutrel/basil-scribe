from django.urls import path

from . import views

app_name = "drafts"

urlpatterns = [
    path("", views.home, name="home"),
    path("generate/", views.generate, name="generate"),
    path("regenerate/", views.regenerate, name="regenerate"),
    path("drafts/", views.draft_list, name="draft_list"),
    path("drafts/<int:pk>/accept/", views.accept_draft, name="accept"),
    path("drafts/<int:pk>/add-precedent/", views.add_precedent, name="add_precedent"),
]
