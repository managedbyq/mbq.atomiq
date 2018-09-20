from django.core.management.base import BaseCommand

import arrow

import rollbar

from ... import constants, models


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=constants.DEFAULT_DAYS_TO_KEEP_OLD_TASKS)
        parser.add_argument('--minutes', type=int)

    def handle(self, *args, **options):
        try:
            minutes = options['minutes']
            if minutes:
                time_to_delete_before = arrow.utcnow().shift(minutes=-minutes)
            else:
                days = options['days']
                time_to_delete_before = arrow.utcnow().shift(days=-days)

            for model in [models.SNSTask, models.SQSTask, models.CeleryTask]:
                model.objects.filter(
                    state__in=[constants.TaskStates.SUCCEEDED, constants.TaskStates.DELETED],
                    created_at__lt=time_to_delete_before.datetime,
                ).delete()

        except Exception:
            rollbar.report_exc_info()
            raise
