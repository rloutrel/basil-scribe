import logging

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import translation
from django.utils.translation import gettext as _

from core import llm
from profiles.middleware import activate_profile_language
from profiles.models import Profile

from ...models import Precedent
from ...prompts import classification_prompt

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Classify precedent replies into the profile's answer categories."

    def add_arguments(self, parser):
        parser.add_argument("--profile", required=True, help="Profile name.")
        parser.add_argument(
            "--type",
            dest="request_type",
            help="Restrict classification to one request type.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Classify at most N precedents (default: all unclassified).",
        )

    def handle(self, *args, **options):
        try:
            profile = Profile.objects.get(name=options["profile"])
        except Profile.DoesNotExist:
            raise CommandError("Profile '%s' not found." % options["profile"])

        qs = Precedent.objects.filter(profile=profile).order_by(
            "-request_mail__date"
        )
        if options["request_type"]:
            qs = qs.filter(request_type=options["request_type"])
        qs = qs.filter(Q(answer_category="") | Q(answer_category__isnull=True))
        precedents = list(qs)
        if options["limit"]:
            precedents = precedents[: options["limit"]]
        if not precedents:
            self.stdout.write("No unclassified precedents.")
            return

        total = len(precedents)
        self.stdout.write(f"Classifying {total} precedent(s)…")
        activate_profile_language(profile)

        done = ok = failed = 0
        for precedent in precedents:
            done += 1
            rt = profile.request_type(precedent.request_type)
            if rt is None:
                failed += 1
                logger.warning(
                    "Precedent %d has unknown request type %s",
                    precedent.pk,
                    precedent.request_type,
                )
                continue
            prompt = classification_prompt(
                profile_language=profile.language,
                type_name=rt["name"],
                categories=rt["answer_categories"],
                request_subject=precedent.request_mail.subject,
                request_body=precedent.request_mail.body,
                reply_body=precedent.reply_mail.body,
            )
            try:
                raw = llm.complete(prompt, temperature=0.0)
            except llm.LLMError:
                failed += 1
                self.stdout.write(self.style.ERROR(f"  [{done}/{total}] LLM call failed"))
                continue
            answer = llm.parse_json_answer(raw)
            category = answer.get("category") or ""
            if category and category in rt["answer_categories"]:
                precedent.answer_category = category
                precedent.save(update_fields=["answer_category"])
                ok += 1
            elif category:
                failed += 1
                logger.warning(
                    "Precedent %d: LLM returned unknown category '%s'",
                    precedent.pk,
                    category,
                )
            else:
                failed += 1
                logger.warning(
                    "Precedent %d: unparseable LLM answer: %.200s",
                    precedent.pk,
                    raw,
                )
            if done % 10 == 0 or done == total:
                self.stdout.write(f"  {done}/{total} classified ({ok} ok, {failed} failed)")

        with translation.override(profile.language):
            self.stdout.write("")
            self.stdout.write(
                _("Classification finished: %(ok)d classified, %(failed)d failed.")
                % {"ok": ok, "failed": failed}
            )
        if failed:
            self.stdout.write(
                self.style.WARNING(
                    _("%(failed)d classification(s) failed; re-run to retry them.")
                    % {"failed": failed}
                )
            )
