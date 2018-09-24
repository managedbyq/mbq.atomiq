import signal

from django.core.management.base import BaseCommand

import rollbar

from ... import consumers


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

    def add_arguments(self, parser):
        parser.add_argument('--queue', required=True)
        parser.add_argument('--celery-app', required=False)

    def handle(self, *args, **options):
        try:
            queue_name = options['queue']
            if queue_name == 'sns':
                consumer = consumers.SNSConsumer()
            if queue_name == 'sqs':
                consumer = consumers.SQSConsumer()
            if queue_name == 'celery':
                consumer = consumers.CeleryConsumer(celery_app=options['celery_app'])

            while self.signal_handler.should_continue():
                consumer.collect_queue_metrics()
                consumer.run()

        except Exception:
            rollbar.report_exc_info()
            raise
