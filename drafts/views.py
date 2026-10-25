from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from precedents.build import add_precedent_from_draft, recent_extraction_summary

from .models import Draft, GenerationTask
from .tasks import submit


def home(request):
    """Daily-use page: generate a draft from the current request."""
    profile = request.active_profile
    if profile is None:
        return render(request, "drafts/no_profile.html")
    task = None
    task_id = request.session.get("active_task_id")
    if task_id:
        task = GenerationTask.objects.filter(
            pk=task_id, profile=profile
        ).first()
        if task is not None and task.status == "done":
            # The draft section below shows the result; hide the panel.
            task = None
    context = {
        "profile": profile,
        "request_types": [
            {"key": rt.get("key"), "name": rt.get("name")}
            for rt in profile.request_types
        ],
        "extraction_summary": recent_extraction_summary(profile),
        "task": task,
        "drafts": [],
        "selected_type": request.GET.get("type", ""),
    }
    if "draft_payload" in request.session:
        context["draft"] = request.session.pop("draft_payload")
    return render(request, "drafts/home.html", context)


@require_POST
def generate(request):
    """Queue an asynchronous generation; the UI polls the task."""
    profile = request.active_profile
    if profile is None:
        return redirect("drafts:home")
    request_text = (request.POST.get("request_text") or "").strip()
    request_type = request.POST.get("request_type") or ""
    recipient_name = (request.POST.get("recipient_name") or "").strip()
    request_date = (request.POST.get("request_date") or "").strip()
    instructions = (request.POST.get("instructions") or "").strip()
    if not request_text:
        messages.error(request, _("Please paste the text of the request."))
        return redirect("drafts:home")
    if not profile.request_type(request_type):
        messages.error(request, _("Please choose a request type."))
        return redirect("drafts:home")

    task = submit(
        profile,
        request_type,
        request_text,
        recipient_name=recipient_name,
        request_date=request_date,
        instructions=instructions,
    )
    request.session["active_task_id"] = task.pk
    return redirect("drafts:home")


@require_POST
def regenerate(request):
    """Next version: re-queue a generation, excluding selected precedents."""
    profile = request.active_profile
    if profile is None:
        return redirect("drafts:home")
    payload = request.session.get("draft_payload") or {}
    if not payload:
        task_id = request.session.get("active_task_id")
        task = (
            GenerationTask.objects.filter(pk=task_id, profile=profile).first()
            if task_id
            else None
        )
        if task is None:
            return redirect("drafts:home")
        payload = {
            "request_type": task.request_type,
            "request_text": task.request_text,
            "recipient_name": task.recipient_name,
            "request_date": task.request_date,
            "precedents_used": task.precedents_used,
        }
    exclude = [str(e) for e in request.POST.getlist("exclude")]
    precedents = payload.get("precedents_used") or []
    if precedents and not exclude:
        exclude = [str(precedents[0].get("id"))]
    instructions = (request.POST.get("instructions") or "").strip()

    task = submit(
        profile,
        payload["request_type"],
        payload["request_text"],
        recipient_name=payload.get("recipient_name", ""),
        request_date=payload.get("request_date", ""),
        exclude_precedent_ids=exclude,
        instructions=instructions,
    )
    request.session["active_task_id"] = task.pk
    return redirect("drafts:home")


def task_status(request, pk):
    """HTMX poll target: the generation status panel."""
    profile = request.active_profile
    task = get_object_or_404(GenerationTask, pk=pk, profile=profile)
    if task.status == "done":
        request.session["draft_payload"] = {
            "generated_text": task.generated_text,
            "request_text": task.request_text,
            "request_type": task.request_type,
            "recipient_name": task.recipient_name,
            "request_date": task.request_date,
            "instructions": task.instructions,
            "precedents_used": task.precedents_used,
        }
    return render(
        request,
        "drafts/partials/task_status.html",
        {"task": task, "profile": profile},
    )


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
    """Take over: persist the final, human-reviewed version."""
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
    """Add as precedent: feed the accepted pair back."""
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
