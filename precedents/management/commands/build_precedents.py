import logging

from django.core.management.base import BaseCommand, CommandError
from django.utils import translation

from profiles.middleware import activate_profile_language
from profiles.models import Profile

from ... import build

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Extract precedent (request, reply) pairs from the mail archive."

    def add_arguments(self, parser):
        parser.add_argument("--profile", required=True, help="Profile name.")
        parser.add_argument(
            "--rebuild",
            action="store_true",
            help="Also clear the profile's archive mails before extraction.",
        )

    def handle(self, *args, **options):
        try:
            profile = Profile.objects.get(name=options["profile"])
        except Profile.DoesNotExist:
            raise CommandError(
                "Profile '%s' not found. Run check_config --sync first."
                % options["profile"]
            )
        activate_profile_language(profile)

        def progress(done, total, path):
            if done % 500 == 0 or done == total:
                self.stdout.write(f"  {done}/{total} mails parsed…")

        self.stdout.write(f"Extracting precedents for profile '{profile.name}'…")
        report = build.build_precedents(
            profile, rebuild=options["rebuild"], progress=progress
        )
        with translation.override(profile.language):
            from django.utils.translation import gettext as _

            self.stdout.write("")
            self.stdout.write(_("Extraction report"))
            self.stdout.write("----------------")
            self.stdout.write(
                _("Mails parsed: %(count)d") % {"count": report.mails_parsed}
            )
            if report.mails_skipped:
                self.stdout.write(
                    _("Mails skipped (unreadable or empty): %(count)d")
                    % {"count": report.mails_skipped}
                )
            self.stdout.write(
                _("Requests identified: %(count)d")
                % {"count": report.requests_identified}
            )
            for key, count in sorted(report.per_type.items()):
                self.stdout.write(
                    _("  - %(type)s: %(count)d") % {"type": key, "count": count}
                )
            for criterion, count in sorted(report.per_criterion.items()):
                self.stdout.write(
                    _("  - criterion '%(criterion)s': %(count)d")
                    % {"criterion": criterion, "count": count}
                )
            self.stdout.write(
                _("Pairs matched: %(count)d") % {"count": report.pairs_matched}
            )
            self.stdout.write(
                _("Requests without reply: %(count)d")
                % {"count": report.unanswered_requests}
            )
            self.stdout.write(
                _("Heuristic (subject + window) matches: %(count)d")
                % {"count": report.heuristic_matches}
            )
            self.stdout.write(
                _("Unmatched outgoing replies: %(count)d")
                % {"count": report.unmatched_replies}
            )
            if report.ambiguous_matches:
                self.stdout.write(
                    _("Ambiguous mails (first type kept): %(count)d")
                    % {"count": report.ambiguous_matches}
                )
