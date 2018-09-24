import collections

from django.core.management.base import BaseCommand

import rollbar
from mbq.atomiq import _collector, constants, models


class Command(BaseCommand):

    def handle(self, *args, **options):
        try:
            queues = [
                (models.SNSTask, constants.QueueType.SNS),
                (models.SQSTask, constants.QueueType.SQS),
                (models.CeleryTask, constants.QueueType.CELERY)
            ]

            for model, queue_type in queues:
                state_counts = collections.Counter(model.objects.values_list('state', flat=True))

                for state, count in state_counts.items():
                    _collector.gauge(
                        'state_total',
                        count,
                        tags={'state': state, 'queue_type': queue_type}
                    )

        except Exception:
            rollbar.report_exc_info()
            raise
