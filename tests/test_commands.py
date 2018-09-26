from django.core.management import call_command
from django.test import TestCase

import arrow
from mbq.atomiq import constants, models
from mbq.atomiq.management.commands import atomic_run_consumer
from tests.compat import mock

import freezegun


@mock.patch('mbq.atomiq.management.commands.atomic_run_consumer.SignalHandler')
class RunConsumerCommandTest(TestCase):

    @mock.patch('mbq.atomiq.management.commands.atomic_run_consumer.consumers.SNSConsumer.run')
    def test_run_consumer_sns(self, run, SignalHandlerMock):
        SignalHandlerMock.return_value.should_continue.side_effect = [True, True, False]
        call_command('atomic_run_consumer', '--queue=sns')
        self.assertEqual(run.call_count, 2)

    @mock.patch('mbq.atomiq.management.commands.atomic_run_consumer.consumers.SQSConsumer.run')
    def test_run_consumer_sqs(self, run, SignalHandlerMock):
        SignalHandlerMock.return_value.should_continue.side_effect = [True, True, False]
        call_command('atomic_run_consumer', '--queue=sqs')
        self.assertEqual(run.call_count, 2)

    @mock.patch('mbq.atomiq.management.commands.atomic_run_consumer.consumers.CeleryConsumer.run')
    def test_run_consumer_celery(self, run, SignalHandlerMock):
        SignalHandlerMock.return_value.should_continue.side_effect = [True, True, False]
        call_command('atomic_run_consumer', '--queue=celery', '--celery-app=tests.celery')
        self.assertEqual(run.call_count, 2)


@mock.patch('mbq.atomiq.constants.DEFAULT_DAYS_TO_KEEP_OLD_TASKS', 30)
class ClenupTasksTest(TestCase):

    def test_cleanup(self, *args):
        command = atomic_run_consumer.Command()

        now_datetime = arrow.utcnow()
        days_before_now_10 = now_datetime.shift(days=-10)
        days_before_now_30 = now_datetime.shift(days=-30)
        days_before_now_31 = now_datetime.shift(days=-31)

        with freezegun.freeze_time(days_before_now_31.datetime):
            # These tasks are in states that should never be deleted,
            # but they were created prior to 30 days before the cleanup task runs.
            # Therefore, if there is a bug causing the cleanup task to accidentally
            # pick up tasks in these states, this test might catch it.
            task_ready = models.SNSTask.objects.create(
                state=constants.TaskStates.ENQUEUED,
            )
            task_failed = models.SNSTask.objects.create(
                state=constants.TaskStates.FAILED,
            )

        with freezegun.freeze_time(days_before_now_30.datetime):
            # These tasks were created exactly 30 days before the cleanup task runs.
            # Since the logic is we delete tasks from strictly before 30 days ago,
            # these tasks should also not be deleted.
            task_deleted1 = models.SNSTask.objects.create(
                state=constants.TaskStates.DELETED,
            )
            task_processed1 = models.SNSTask.objects.create(
                state=constants.TaskStates.SUCCEEDED,
            )

        with freezegun.freeze_time(days_before_now_10.datetime):
            # These tasks are in the 2 states that we do delete old tasks for.
            # They were created more recently than 30 days, so they should not be deleted
            task_deleted2 = models.SNSTask.objects.create(
                state=constants.TaskStates.DELETED,
            )
            task_processed2 = models.SNSTask.objects.create(
                state=constants.TaskStates.SUCCEEDED,
            )

        with freezegun.freeze_time(days_before_now_31.datetime):
            # These tasks are in the 2 states that we do delete and they
            # were created more than 30 days ago, so they should be deleted
            task_deleted3 = models.SNSTask.objects.create(
                state=constants.TaskStates.DELETED,
            )
            task_processed3 = models.SNSTask.objects.create(
                state=constants.TaskStates.SUCCEEDED,
            )

        with freezegun.freeze_time(now_datetime.datetime):
            command.cleanup_old_tasks('sns')

            self.assertTrue(models.SNSTask.objects.filter(id=task_ready.id).exists())
            self.assertTrue(models.SNSTask.objects.filter(id=task_failed.id).exists())
            self.assertTrue(models.SNSTask.objects.filter(id=task_deleted1.id).exists())
            self.assertTrue(models.SNSTask.objects.filter(id=task_processed1.id).exists())
            self.assertTrue(models.SNSTask.objects.filter(id=task_deleted2.id).exists())
            self.assertTrue(models.SNSTask.objects.filter(id=task_processed2.id).exists())
            self.assertFalse(models.SNSTask.objects.filter(id=task_deleted3.id).exists())
            self.assertFalse(models.SNSTask.objects.filter(id=task_processed3.id).exists())
