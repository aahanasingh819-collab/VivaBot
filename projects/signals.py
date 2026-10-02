from django.db.models.signals import post_delete
from django.dispatch import receiver

from projects.models import Project


@receiver(post_delete, sender=Project)
def delete_project_report(sender, instance, **kwargs):
    if instance.report_file:
        instance.report_file.delete(save=False)