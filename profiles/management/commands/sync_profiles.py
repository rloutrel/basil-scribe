from django.core.management.base import BaseCommand

from profiles.sync import sync_all


class Command(BaseCommand):
    help = "Load and validate every profile YAML file, then sync them to the database."

    def handle(self, *args, **options):
        results = sync_all()
        for name, success, errors in results:
            if success:
                self.stdout.write(f"Profile '{name}': OK, synced.")
            else:
                self.stderr.write(f"Profile '{name}': INVALID")
                for error in errors:
                    self.stderr.write(f"  - {error}")
        if not results:
            self.stdout.write("No profile files found.")
