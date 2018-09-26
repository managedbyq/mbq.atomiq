import collections
import signal

from django.core.management.base import BaseCommand

import arrow

import rollbar

from ... import _collector, constants, consumers, utils


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

    def cleanup_old_tasks(self, queue_type):
        days_to_keep_old_tasks = constants.DEFAULT_DAYS_TO_KEEP_OLD_TASKS
        time_to_delete_before = arrow.utcnow().shift(days=-days_to_keep_old_tasks)

        model = self.consumers[queue_type].model
        model.objects.filter(
            state__in=[constants.TaskStates.SUCCEEDED, constants.TaskStates.DELETED],
            created_at__lt=time_to_delete_before.datetime,
        ).delete()

    @utils.debounce(minutes=15)
    def run_delayed_cleanup(self, **options):
        self.cleanup_old_tasks(options['queue'])

    @utils.debounce(seconds=15)
    def collect_metrics(self, **options):
        queue_type = options['queue']
        model = self.consumers[queue_type].model

        state_counts = collections.Counter(model.objects.values_list('state', flat=True))
        task_states = (state[0] for state in constants.TaskStates.CHOICES)

        for task_state in task_states:
            _collector.gauge(
                'state_total',
                state_counts.get(task_state, 0),
                tags={'state': task_state, 'queue_type': queue_type},
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
                self.run_delayed_cleanup(**options)

        except Exception:
            rollbar.report_exc_info()
            raise
