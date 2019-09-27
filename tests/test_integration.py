import json
from unittest import mock

from django.core.management import call_command
from django.db import transaction
from django.test import TestCase

import mbq.atomiq


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

        boto_client.assert_called_once_with('sns', endpoint_url=None)
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

    @mock.patch('importlib.import_module')
    def test_celery_task_runs(self, import_module):
        test_task = mock.MagicMock()
        test_task.name = 'task_module.test_task'

        import_module.return_value = mock.MagicMock(test_task=test_task)

        with transaction.atomic():
            mbq.atomiq.celery_publish(test_task, 'one', 2, False, test=True)
            mbq.atomiq.celery_publish(test_task, 3, 'two', True, test='Hello')

        call_command('atomic_run_consumer', '--queue=celery')

        import_module.assert_called_with('task_module')

        celery_calls = [
            mock.call('one', 2, False, test=True),
            mock.call(3, 'two', True, test='Hello'),
        ]
        test_task.delay.assert_has_calls(celery_calls)
