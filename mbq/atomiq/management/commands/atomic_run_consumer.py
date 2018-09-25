import collections
import signal

from django.core.management.base import BaseCommand

import arrow

import rollbar

from ... import _collector, constants, consumers, utils


CLEANUP_DELAY_MINUTES = 15


class SignalHandler():

    def __init__(self):
        self._interrupted = False

    def handle_signal(self, *args, **kwargs):
        self._interrupted = True

    def should_continue(self):
        return not self._interrupted


class Command(BaseCommand):

    def __init__(self, *args, **kwargs):
        super(BaseCommand, self).__init__(*args, **kwargs)

        self.signal_handler = SignalHandler()
        signal.signal(signal.SIGINT, self.signal_handler.handle_signal)
        signal.signal(signal.SIGTERM, self.signal_handler.handle_signal)
        signal.signal(signal.SIGQUIT, self.signal_handler.handle_signal)

        self.consumers = {
            constants.QueueType.SNS: consumers.SNSConsumer,
            constants.QueueType.SQS: consumers.SQSConsumer,
            constants.QueueType.CELERY: consumers.CeleryConsumer,
        }

    def add_arguments(self, parser):
        queue_type_choices = [c[0] for c in constants.QueueType.CHOICES]
        parser.add_argument('--queue', required=True, choices=queue_type_choices)
        parser.add_argument('--celery-app', required=False)

    @utils.debounce(minutes=CLEANUP_DELAY_MINUTES)
    def cleanup_old_tasks(self, **options):
        days_to_keep_old_tasks = constants.DEFAULT_DAYS_TO_KEEP_OLD_TASKS
        time_to_delete_before = arrow.utcnow().shift(days=-days_to_keep_old_tasks)

        model = self.consumers[options['queue']].model
        model.objects.filter(
            state__in=[constants.TaskStates.SUCCEEDED, constants.TaskStates.DELETED],
            created_at__lt=time_to_delete_before.datetime,
        ).delete()

    @utils.debounce(seconds=15)
    def collect_metrics(self, **options):
        queue_type = options['queue']
        model = self.consumers[queue_type].model

        state_counts = collections.Counter(model.objects.values_list('state', flat=True))
        for state, count in state_counts.items():
            _collector.gauge(
                'state_total',
                count,
                tags={'state': state, 'queue_type': queue_type},
            )

    def handle(self, *args, **options):
        try:
            queue_type = options['queue']

            Consumer = self.consumers[queue_type]

            consumer_kwargs = {}
            if queue_type == constants.QueueType.CELERY:
                consumer_kwargs['celery_app'] = options['celery_app']

            consumer = Consumer(**consumer_kwargs)

            while self.signal_handler.should_continue():
                consumer.run()
                self.collect_metrics(**options)
                self.cleanup_old_tasks(**options)

        except Exception:
            rollbar.report_exc_info()
            raise
