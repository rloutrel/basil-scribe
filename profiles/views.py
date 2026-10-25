from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from .middleware import set_active_profile


@require_POST
def select_profile(request):
    profile = set_active_profile(request, request.POST.get("profile", ""))
    return redirect(request.POST.get("next") or "drafts:home")
