import json

from django.core.management import call_command
from django.db import transaction
from django.test import TestCase

import mbq.atomiq
from tests.celery import celery_app
from tests.compat import mock


class ProcessTasksTest(TestCase):

    def setUp(self):
        signal_handler = mock.patch(
            'mbq.atomiq.management.commands.atomic_run_consumer.SignalHandler'
        )
        signal_handler_mock = signal_handler.start()
        signal_handler_mock.return_value.should_continue.side_effect = [True, True, False]
        self.addCleanup(signal_handler_mock.stop)

    @mock.patch('boto3.client')
    def test_sns_task_runs(self, boto_client):
        sns_client = mock.MagicMock()
        boto_client.return_value = sns_client

        with transaction.atomic():
            mbq.atomiq.sns_publish('topic_arn1', {'sns1': 'sns1'})
            mbq.atomiq.sns_publish('topic_arn2', {'sns2': 'sns2'})

        call_command('atomic_run_consumer', '--queue=sns')

        boto_client.assert_called_once_with('sns')
        sns_calls = [
            mock.call(
                TargetArn='topic_arn1',
                MessageStructure='json',
                Message=json.dumps({'default': json.dumps({'sns1': 'sns1'})})
            ),
            mock.call(
                TargetArn='topic_arn2',
                MessageStructure='json',
                Message=json.dumps({'default': json.dumps({'sns2': 'sns2'})})
            ),
        ]
        sns_client.publish.assert_has_calls(sns_calls)

    @mock.patch('boto3.client')
    def test_sqs_task_runs(self, boto_client):
        sqs_client = mock.MagicMock()
        boto_client.return_value = sqs_client

        with transaction.atomic():
            mbq.atomiq.sqs_publish('queue_url1', {'sqs1': 'sqs1'})
            mbq.atomiq.sqs_publish('queue_url2', {'sqs2': 'sqs2'})

        call_command('atomic_run_consumer', '--queue=sqs')

        boto_client.assert_called_once_with('sqs')
        sqs_calls = [
            mock.call(
                QueueUrl='queue_url1',
                MessageBody=json.dumps({'Message': json.dumps({'sqs1': 'sqs1'})})
            ),
            mock.call(
                QueueUrl='queue_url2',
                MessageBody=json.dumps({'Message': json.dumps({'sqs2': 'sqs2'})})
            ),
        ]
        sqs_client.send_message.assert_has_calls(sqs_calls)

    @mock.patch.dict(celery_app.tasks, {'test_task': mock.MagicMock()})
    def test_celery_task_runs(self):
        test_task = mock.MagicMock()
        test_task.name = 'test_task'

        with transaction.atomic():
            mbq.atomiq.celery_publish(test_task, 'one', 2, False, test=True)
            mbq.atomiq.celery_publish(test_task, 3, 'two', True, test='Hello')

        call_command('atomic_run_consumer', '--queue=celery', '--celery-app=tests.celery')

        celery_calls = [
            mock.call('one', 2, False, test=True),
            mock.call(3, 'two', True, test='Hello'),
        ]
        celery_app.tasks['test_task'].delay.assert_has_calls(celery_calls)
