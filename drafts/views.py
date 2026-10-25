from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.llm import LLMError
from precedents.build import add_precedent_from_draft, recent_extraction_summary

from .generation import generate_draft
from .models import Draft


def home(request):
    """Daily-use page: generate a draft from the current request."""
    profile = request.active_profile
    if profile is None:
        return render(request, "drafts/no_profile.html")
    context = {
        "profile": profile,
        "request_types": [
            {"key": rt.get("key"), "name": rt.get("name")}
            for rt in profile.request_types
        ],
        "extraction_summary": recent_extraction_summary(profile),
        "draft": None,
        "precedents_used": [],
        "drafts": [],
        "selected_type": request.GET.get("type", ""),
    }
    if "draft_payload" in request.session:
        payload = request.session.pop("draft_payload")
        context["draft"] = payload
    return render(request, "drafts/home.html", context)


@require_POST
def generate(request):
    """Generate a draft for the profile's selected request type."""
    profile = request.active_profile
    if profile is None:
        return redirect("drafts:home")
    request_text = (request.POST.get("request_text") or "").strip()
    request_type = request.POST.get("request_type") or ""
    recipient_name = (request.POST.get("recipient_name") or "").strip()
    request_date = (request.POST.get("request_date") or "").strip()
    if not request_text:
        messages.error(request, _("Please paste the text of the request."))
        return redirect("drafts:home")
    if not profile.request_type(request_type):
        messages.error(request, _("Please choose a request type."))
        return redirect("drafts:home")

    try:
        draft_text, precedents_used = generate_draft(
            profile,
            request_type,
            request_text,
            recipient_name=recipient_name,
            request_date=request_date,
        )
    except LLMError as exc:
        messages.error(
            request,
            _("Draft generation failed: %(error)s") % {"error": exc},
        )
        return redirect("drafts:home")

    payload = {
        "generated_text": draft_text,
        "request_text": request_text,
        "request_type": request_type,
        "recipient_name": recipient_name,
        "request_date": request_date,
        "precedents_used": precedents_used,
    }
    request.session["draft_payload"] = payload
    return redirect("drafts:home")


@require_POST
def regenerate(request):
    """Version suivante: regenerate, excluding the selected precedent."""
    profile = request.active_profile
    if profile is None:
        return redirect("drafts:home")
    payload = request.session.get("draft_payload")
    if not payload:
        return redirect("drafts:home")
    exclude = request.POST.getlist("exclude")
    exclude_ids = [str(e) for e in exclude]

    precedents = payload.get("precedents_used") or []
    if precedents and not exclude_ids:
        exclude_ids = [str(precedents[0].get("id"))]
    try:
        draft_text, precedents_used = generate_draft(
            profile,
            payload["request_type"],
            payload["request_text"],
            recipient_name=payload.get("recipient_name", ""),
            request_date=payload.get("request_date", ""),
            exclude_precedent_ids=exclude_ids,
        )
    except LLMError as exc:
        messages.error(
            request,
            _("Draft generation failed: %(error)s") % {"error": exc},
        )
        return redirect("drafts:home")
    payload["generated_text"] = draft_text
    payload["precedents_used"] = precedents_used
    payload["excluded"] = sorted(
        set(payload.get("excluded", []) + [str(e) for e in exclude_ids])
    )
    request.session["draft_payload"] = payload
    return redirect("drafts:home")


def draft_list(request):
    """Step 4 — history of drafts, filterable by profile and type."""
    profile = request.active_profile
    if profile is None:
        return render(request, "drafts/no_profile.html")
    qs = Draft.objects.filter(profile=profile)
    type_filter = request.GET.get("type", "")
    if type_filter:
        qs = qs.filter(request_type=type_filter)
    status_filter = request.GET.get("status", "")
    if status_filter:
        qs = qs.filter(status=status_filter)
    return render(
        request,
        "drafts/draft_list.html",
        {
            "profile": profile,
            "drafts": qs[:100],
            "type_filter": type_filter,
            "status_filter": status_filter,
            "request_types": [
                {"key": rt.get("key"), "name": rt.get("name")}
                for rt in profile.request_types
            ],
        },
    )


@require_POST
def accept_draft(request, pk):
    """Übernehmen: persist the final, human-reviewed version."""
    draft = get_object_or_404(Draft, pk=pk, profile=request.active_profile)
    final_text = (request.POST.get("final_text") or "").strip()
    if not final_text:
        messages.error(request, _("The final version cannot be empty."))
        return redirect("drafts:draft_list")
    draft.final_text = final_text
    draft.status = "accepted"
    draft.save(update_fields=["final_text", "status", "updated_at"])
    messages.success(request, _("Draft saved."))
    return redirect("drafts:draft_list")


@require_POST
def add_precedent(request, pk):
    """Als Präzedenzfall hinzufügen: feed the accepted pair back."""
    draft = get_object_or_404(
        Draft, pk=pk, profile=request.active_profile, status="accepted"
    )
    if draft.added_as_precedent:
        messages.info(request, _("This draft is already a precedent."))
        return redirect("drafts:draft_list")
    precedent = add_precedent_from_draft(draft)
    messages.success(
        request,
        _("Precedent #%(id)d added to the profile index.")
        % {"id": precedent.pk},
    )
    return redirect("drafts:draft_list")
