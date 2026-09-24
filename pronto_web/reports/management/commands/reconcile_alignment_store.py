"""Inspect and, during a maintenance pause, remove unreferenced managed pairs."""

from datetime import timedelta
from pathlib import Path
import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from pronto_web.reports.alignment_config import alignment_saving_enabled
from pronto_web.reports.alignment_store import PublishedPair, UnsafeAlignmentPath, remove_pair
from pronto_web.reports.models import AlignmentUploadSession, SavedAlignment


OPAQUE_NAME = re.compile(r"[0-9a-f]{32}\Z")
TEMPORARY_NAME = re.compile(r"\.[0-9a-f]{32}\.tmp\Z")


class Command(BaseCommand):
    help = "Find orphan managed alignment pairs; --delete removes only old, unreferenced pairs."

    def add_arguments(self, parser):
        parser.add_argument("--delete", action="store_true")
        parser.add_argument("--minimum-age-hours", type=int, default=48)

    def handle(self, *args, **options):
        if not alignment_saving_enabled(settings):
            raise CommandError("Alignment preservation gate is not enabled")
        if options["minimum_age_hours"] < 24:
            raise CommandError("Orphan grace period must be at least 24 hours")
        root = Path(settings.PRONTO_ALIGNMENT_STORE_ROOT)
        if root.is_symlink() or not root.is_dir():
            raise CommandError("Private managed root is unavailable")
        root = root.resolve(strict=True)
        if options["delete"] and AlignmentUploadSession.objects.filter(
            state__in=["OPEN", "VALIDATING"], expires_at__gt=timezone.now(),
        ).exists():
            raise CommandError("Pause new saves and finish active upload sessions first")
        cutoff = (timezone.now() - timedelta(hours=options["minimum_age_hours"])).timestamp()
        candidates = 0
        for directory in root.iterdir():
            final = bool(OPAQUE_NAME.fullmatch(directory.name))
            temporary = bool(TEMPORARY_NAME.fullmatch(directory.name))
            if not final and not temporary:
                continue  # Never touch unknown entries.
            if directory.is_symlink() or not directory.is_dir():
                raise CommandError("Unsafe managed directory encountered")
            key = directory.name
            if final and (SavedAlignment.objects.filter(data_key=f"{key}/data").exists() or
                          SavedAlignment.objects.filter(index_key=f"{key}/index").exists()):
                continue  # READY and DELETING records both retain ownership.
            data, index = directory / "data", directory / "index"
            contents = set(directory.iterdir())
            if (not contents or not contents <= {data, index} or
                    (final and contents != {data, index}) or
                    any(path.is_symlink() or not path.is_file() for path in contents)):
                raise CommandError("Unreferenced managed directory has unsafe contents")
            if max(directory.stat().st_mtime, *(path.stat().st_mtime for path in contents)) > cutoff:
                continue
            candidates += 1
            if options["delete"]:
                try:
                    if final:
                        pair = PublishedPair(root, directory, data, index, f"{key}/data", f"{key}/index",
                                             0, 0, "", "")
                        remove_pair(pair)
                    else:
                        for path in contents:
                            path.unlink()
                        directory.rmdir()
                except (OSError, UnsafeAlignmentPath) as exc:
                    raise CommandError("Could not safely remove orphan managed pair") from exc
        self.stdout.write(f"Old orphan managed alignment pairs: {candidates}")
