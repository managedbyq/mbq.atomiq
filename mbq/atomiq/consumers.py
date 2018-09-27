import importlib
import json
import traceback

from django.db import transaction

import arrow

from . import constants, exceptions, models


class BaseConsumer(object):

    @transaction.atomic
    def process_one_task(self):
        task = self.get_next_enqueued_task()

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
            else:
                # Task will be retried. It will be put back on the queue and made
                # invisible to the consumer using an exponential backoff policy.
                backoff_time = 2**task.number_of_attempts
                task.visible_after = arrow.utcnow().shift(seconds=backoff_time).datetime
        else:
            task.state = constants.TaskStates.SUCCEEDED
            task.succeeded_at = arrow.utcnow().datetime

        task.save()

        return task

    def get_next_enqueued_task(self):
        task = self.model.objects.available_for_processing()[:1].select_for_update().first()

        if not task:
            raise exceptions.NoAvailableTasksToProcess()

        return task

    def publish(self, task):
        raise NotImplementedError('publish must be implemented by subclasses.')


class SNSConsumer(BaseConsumer):
    model = models.SNSTask
    queue_type = constants.QueueType.SNS
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
    queue_type = constants.QueueType.SQS
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
    queue_type = constants.QueueType.CELERY
    celery_app = None

    def __init__(self, celery_app):
        self.celery_app = importlib.import_module(celery_app).celery_app

    def publish(self, task):
        celery_task = self.celery_app.tasks[task.task_name]
        celery_task.delay(*task.task_arguments['args'], **task.task_arguments['kwargs'])
