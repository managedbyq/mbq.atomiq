import importlib
import json
import traceback
from time import sleep

from django.db import transaction

import arrow

import rollbar

from . import _collector, constants, models, utils


class BaseConsumer(object):

    def run(self):
        try:
            with transaction.atomic():
                task = self.model.objects.available_for_processing()[:1].select_for_update().get()
                execution_started_at = arrow.utcnow()
                self.process_task(task)
                execution_ended_at = arrow.utcnow()
            self.send_task_execution_metrics(task, execution_started_at, execution_ended_at)
        except self.model.DoesNotExist:
            sleep(0.5)
        except Exception:
            rollbar.report_exc_info()
            sleep(0.5)

    def process_task(self, task):
        task.number_of_attempts += 1
        try:
            self.publish(task)
        except Exception as e:
            if task.number_of_attempts >= constants.MAX_ATTEMPTS_TO_PROCESS_TASKS:
                # Task exceeded max retry attempts. It will be moved to the FAILED state
                # to remove it from automatic processing.
                task.state = constants.TaskStates.FAILED
                task.failed_at = arrow.utcnow().datetime
                task.error_message = str(e)
                task.stacktrace = traceback.format_exc()
                rollbar.report_exc_info()
            else:
                # Task will be retried. It will be put back on the queue and made
                # invisible to the consumer using an exponential backoff policy.
                backoff_time = 2**task.number_of_attempts
                task.visible_after = arrow.utcnow().shift(seconds=backoff_time).datetime
        else:
            # Task execution succeeded.
            task.state = constants.TaskStates.SUCCEEDED
            task.succeeded_at = arrow.utcnow().datetime

        task.save()

    def send_task_execution_metrics(self, task, execution_started_at, execution_ended_at):
        dd_tags = {
            'end_state': task.state,
            'result': 'success' if task.state == constants.TaskStates.SUCCEEDED else 'error',
            'queue_type': self.queue_type,
        }
        _collector.increment(
            'task',
            tags=dd_tags,
        )

        _collector.timing(
            'task.wait_time_ms',
            utils.time_difference_ms(task.visible_after, execution_started_at),
            tags=dd_tags,
        )
        _collector.timing(
            'task.execution_time_ms',
            utils.time_difference_ms(execution_started_at, execution_ended_at),
            tags=dd_tags,
        )
        if task.state == constants.TaskStates.SUCCEEDED:
            _collector.timing(
                'task.turnaround_time_ms',
                utils.time_difference_ms(task.created_at, task.succeeded_at),
                tags=dd_tags,
            )

    def publish(self, task):
        raise NotImplementedError('publish must be implemented by subclasses.')

    def collect_queue_metrics(self):
        for state in constants.TaskStates.CHOICES:
            state = state[0]
            _collector.gauge(
                'state_total',
                self.model.objects.filter(state=state).count(),
                tags={'state': state, 'queue_type': self.queue_type},
            )


class SNSConsumer(BaseConsumer):
    model = models.SNSTask
    queue_type = 'sns'
    sns_client = None

    def __init__(self):
        import boto3
        self.sns_client = boto3.client('sns')

    def publish(self, task):
        self.sns_client.publish(
            TargetArn=task.topic_arn,
            MessageStructure='json',
            Message=json.dumps({
                'default': json.dumps(task.payload),
            }),
        )


class SQSConsumer(BaseConsumer):
    model = models.SQSTask
    queue_type = 'sqs'
    sqs_client = None

    def __init__(self):
        import boto3
        self.sqs_client = boto3.client('sqs')

    def publish(self, task):
        self.sqs_client.send_message(
            QueueUrl=task.queue_url,
            MessageBody=json.dumps({
                'Message': json.dumps(task.payload),
            })
        )


class CeleryConsumer(BaseConsumer):
    model = models.CeleryTask
    queue_type = 'celery'
    celery_app = None

    def __init__(self, celery_app):
        self.celery_app = importlib.import_module(celery_app).celery_app

    def publish(self, task):
        celery_task = self.celery_app.tasks[task.task_name]
        celery_task.delay(*task.task_arguments['args'], **task.task_arguments['kwargs'])
