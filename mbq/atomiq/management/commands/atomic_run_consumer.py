from __future__ import absolute_import, print_function, unicode_literals

import signal
from time import sleep

from django.core.management.base import BaseCommand

import rollbar

import jaws
from ... import consumers


INTERRUPTED_BY_SIGNAL = False


def signal_handler(signal, frame):
    global INTERRUPTED_BY_SIGNAL
    INTERRUPTED_BY_SIGNAL = True


def should_continue():
    return not INTERRUPTED_BY_SIGNAL


class Command(BaseCommand):
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

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGQUIT, signal_handler)

            while should_continue():
                if jaws.open('enable-atomiq-consumer', False):
                    consumer.collect_queue_metrics()
                    consumer.run()
                else:
                    sleep(10)

        except Exception:
            rollbar.report_exc_info()
            raise
