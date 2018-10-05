import uuid

import django.utils.timezone
from django.db import models

import arrow
from jsonfield import JSONField

from . import constants


class TaskManager(models.Manager):
    def available_for_processing(self):
        return super(TaskManager, self).get_queryset().filter(
            state=constants.TaskStates.ENQUEUED,
            visible_after__lte=arrow.utcnow().datetime,
        ).order_by('visible_after')


class Task(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    succeeded_at = models.DateTimeField(null=True)
    deleted_at = models.DateTimeField(null=True)
    failed_at = models.DateTimeField(null=True)

    number_of_attempts = models.PositiveIntegerField(default=0)
    visible_after = models.DateTimeField(default=django.utils.timezone.now)
    error_message = models.TextField(null=True)
    stacktrace = models.TextField(null=True)
    state = models.CharField(
        choices=constants.TaskStates.CHOICES,
        max_length=256,
        default=constants.TaskStates.ENQUEUED,
    )
    objects = TaskManager()

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['state', 'visible_after'])
        ]


class SNSTask(Task):
    topic_arn = models.CharField(max_length=256)
    payload = JSONField()

    class Meta(Task.Meta):
        verbose_name = 'SNS Task'


class SQSTask(Task):
    queue_url = models.CharField(max_length=256)
    payload = JSONField()

    class Meta(Task.Meta):
        verbose_name = 'SQS Task'


class CeleryTask(Task):
    task_name = models.CharField(max_length=256)
    task_arguments = JSONField(dump_kwargs={})

    class Meta(Task.Meta):
        verbose_name = 'Celery Task'
