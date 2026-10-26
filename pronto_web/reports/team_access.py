"""Explicit report grants for the installation's ordinary PRONTO team."""
TEAM_GROUP = 'PRONTO report team'


def grant_imported_report(report, actor):
    from django.contrib.auth import get_user_model
    from .models import ReportGrant
    recipients = {actor.pk}
    if actor.groups.filter(name=TEAM_GROUP).exists():
        report.team_shared = True
        report.save(update_fields=['team_shared'])
        recipients.update(get_user_model().objects.filter(is_active=True, groups__name=TEAM_GROUP)
                          .values_list('pk', flat=True))
    ReportGrant.objects.bulk_create([ReportGrant(report=report, user_id=pk) for pk in recipients],
                                   ignore_conflicts=True)
