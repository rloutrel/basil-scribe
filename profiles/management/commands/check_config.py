from django.core.management.base import BaseCommand, CommandError
from django.utils import translation

from core import config


class Command(BaseCommand):
    help = "Validate one or all profile YAML files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--profile",
            help="Profile name (file stem) to validate; all when omitted.",
        )
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Also sync valid profiles into the database.",
        )

    def handle(self, *args, **options):
        if options["profile"]:
            names = [options["profile"]]
        else:
            names = config.available_profile_names()
            if not names:
                self.stdout.write("No profile files found in the profiles directory.")
                return

        failures = 0
        for name in names:
            try:
                cfg = config.load_profile(name)
            except config.ConfigError as exc:
                failures += 1
                language = "en"
                self.stderr.write(f"Profile '{name}' is INVALID:")
                for error in [str(exc)] + [str(e) for e in exc.errors]:
                    self.stderr.write(f"  - {error}")
                continue
            with translation.override(cfg.language):
                self.stdout.write(f"Profile '{name}': OK ({cfg.request_types and len(cfg.request_types) or 0} request types)")
            if options["sync"]:
                from profiles.sync import sync_profile

                sync_profile(cfg)
                self.stdout.write(f"Profile '{name}': synced.")

        if failures:
            raise CommandError(f"{failures} profile(s) invalid.")
