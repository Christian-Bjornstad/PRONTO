"""Remove only expired, opaque upload staging files; never saved READY pairs."""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from pronto_web.reports.alignment_commands import _cleanup
from pronto_web.reports.alignment_store import UnsafeAlignmentPath
from pronto_web.reports.models import AlignmentUploadSession


class Command(BaseCommand):
    help = "Remove expired private alignment staging bytes; never touch READY saved pairs."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Count expired sessions without deleting files.")

    def handle(self, *args, **options):
        raw_root = settings.PRONTO_ALIGNMENT_STAGING_ROOT
        if not raw_root:
            raise CommandError("Private staging root is not configured")
        root = Path(raw_root)
        if root.is_symlink() or not root.is_dir():
            raise CommandError("Private staging root is unavailable")
        root = root.resolve(strict=True)
        project = Path(settings.BASE_DIR).resolve(strict=True)
        if root == project or project in root.parents:
            raise CommandError("Private staging root must be outside the project")
        now = timezone.now()
        count = 0
        for session_id in AlignmentUploadSession.objects.filter(expires_at__lte=now).values_list("pk", flat=True):
            with transaction.atomic():
                session = AlignmentUploadSession.objects.select_for_update().get(pk=session_id)
                if session.expires_at > timezone.now():
                    continue
                count += 1
                if options["dry_run"]:
                    continue
                try:
                    _cleanup(session)
                except (OSError, UnsafeAlignmentPath) as exc:
                    raise CommandError("Expired staging record has unsafe or unavailable files") from exc
                if session.state in {"OPEN", "VALIDATING"}:
                    session.state = "FAILED"
                    session.save(update_fields=["state"])
        self.stdout.write(f"Expired alignment staging sessions: {count}")
