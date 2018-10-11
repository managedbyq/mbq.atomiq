from unittest import mock

from django.test import TestCase

import arrow
from mbq.atomiq import consumers
from mbq.atomiq.constants import MAX_ATTEMPTS_TO_PROCESS_TASKS, TaskStates
from mbq.atomiq.models import SNSTask

import freezegun


@mock.patch('mbq.atomiq.consumers.SNSConsumer.publish')
class ProcessTasksTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.consumer = consumers.SNSConsumer()

    def test_process_tasks_successfully(self, publish):
        task = SNSTask.objects.create()
        self.consumer.process_one_task()
        task.refresh_from_db()
        self.assertEquals(task.state, TaskStates.SUCCEEDED)
        self.assertEquals(task.number_of_attempts, 1)
        self.assertIsNotNone(task.succeeded_at)

    def test_process_tasks_with_requeue(self, publish):
        # Makes publish raise an exception so the tasks fail
        publish.side_effect = Exception
        task = SNSTask.objects.create()

        attempt = 1
        with freezegun.freeze_time() as frozen_time:
            while attempt < MAX_ATTEMPTS_TO_PROCESS_TASKS:
                self.consumer.process_one_task()

                task.refresh_from_db()

                expected_visible_after = arrow.utcnow().shift(seconds=2**attempt)
                self.assertEquals(task.state, TaskStates.ENQUEUED)
                self.assertEquals(task.number_of_attempts, attempt)
                self.assertEquals(task.visible_after, expected_visible_after)

                attempt += 1
                frozen_time.tick(delta=(expected_visible_after - arrow.utcnow()))

    def test_process_tasks_with_final_failure(self, publish):
        # Change number_of_attempts so the consumer thinks this is the last retry
        task = SNSTask.objects.create()
        task.number_of_attempts = MAX_ATTEMPTS_TO_PROCESS_TASKS - 1
        task.save()

        # Makes publish raise an exception so the tasks fail
        publish.side_effect = Exception('Test Error Message')
        self.consumer.process_one_task()
        task.refresh_from_db()
        # These tasks should be processed with an exception raised in the publish function.
        # Since they have already been retried the max number of times,
        # they should be transitioned to the FAILED state.
        self.assertEquals(task.state, TaskStates.FAILED)
        self.assertEquals(task.number_of_attempts, MAX_ATTEMPTS_TO_PROCESS_TASKS)
        self.assertIsNotNone(task.failed_at)
        self.assertEquals(task.error_message, 'Test Error Message')
        # A hacky way of testing that the stacktrace field is being set to something
        # that is likely an actual stacktrace.
        # Using assertEquals on the stacktrace field would be a very brittle test,
        # since refactoring the code would change the stacktrace and break the tests.
        self.assertTrue(
            'Traceback (most recent call last):' in task.stacktrace
        )

    def test_process_tasks_with_final_success(self, sns_publish):
        # Change number_of_attempts so the consumer thinks this is the last retry
        task = SNSTask.objects.create()
        task.number_of_attempts = MAX_ATTEMPTS_TO_PROCESS_TASKS - 1
        task.save()

        self.consumer.process_one_task()
        task.refresh_from_db()
        # These tasks should be processed successfully and transitioned to SUCCEEDED
        self.assertEquals(task.state, TaskStates.SUCCEEDED)
        self.assertEquals(task.number_of_attempts, MAX_ATTEMPTS_TO_PROCESS_TASKS)
        self.assertIsNotNone(task.succeeded_at)
