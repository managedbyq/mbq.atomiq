from django.core.management import call_command
from django.test import TestCase

import arrow
from mbq.atomiq import constants, models
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
class CleanupCommandTest(TestCase):

    def test_no_args_no_tasks(self):
        # Here we test if that there are no tasks to delete,
        # the command doesn't throw an error.
        call_command('atomic_cleanup_old_tasks')

    def test_args_but_no_tasks(self):
        # Same as above, but this time we pass in an argument.
        call_command('atomic_cleanup_old_tasks', '--days=2')

    def test_no_tasks_to_delete(self):
        for model in [models.SNSTask, models.SQSTask, models.CeleryTask]:
            # This test aims to find the edge cases where tasks should not be deleted and
            # makes sure that they aren't.
            now_datetime = arrow.utcnow()
            days_before_now_10 = now_datetime.shift(days=-10)
            days_before_now_30 = now_datetime.shift(days=-30)
            days_before_now_31 = now_datetime.shift(days=-31)
            with freezegun.freeze_time(days_before_now_31.datetime):
                # These tasks are in states that should never be deleted,
                # but they were created prior to 30 days before the cleanup task runs.
                # Therefore, if there is a bug causing the cleanup task to accidentally
                # pick up tasks in these states, this test might catch it.
                task_ready = model.objects.create(
                    state=constants.TaskStates.ENQUEUED,
                )
                task_failed = model.objects.create(
                    state=constants.TaskStates.FAILED,
                )

            with freezegun.freeze_time(days_before_now_30.datetime):
                # These tasks were created exactly 30 days before the cleanup task runs.
                # Since the logic is we delete tasks from strictly before 30 days ago,
                # these tasks should also not be deleted.
                task_deleted1 = model.objects.create(
                    state=constants.TaskStates.DELETED,
                )
                task_processed1 = model.objects.create(
                    state=constants.TaskStates.SUCCEEDED,
                )
            with freezegun.freeze_time(days_before_now_10.datetime):
                # These tasks are in the 2 states that we do delete old tasks for.
                # They were created more recently than 30 days, so they should not be deleted
                task_deleted2 = model.objects.create(
                    state=constants.TaskStates.DELETED,
                )
                task_processed2 = model.objects.create(
                    state=constants.TaskStates.SUCCEEDED,
                )

            with freezegun.freeze_time(now_datetime.datetime):
                call_command('atomic_cleanup_old_tasks')
                self.assertTrue(model.objects.filter(id=task_ready.id).exists())
                self.assertTrue(model.objects.filter(id=task_failed.id).exists())
                self.assertTrue(model.objects.filter(id=task_deleted1.id).exists())
                self.assertTrue(model.objects.filter(id=task_processed1.id).exists())
                self.assertTrue(model.objects.filter(id=task_deleted2.id).exists())
                self.assertTrue(model.objects.filter(id=task_processed2.id).exists())

    def test_days_arg_works(self):
        now_datetime = arrow.utcnow()
        days_before_now_1 = now_datetime.shift(days=-1)
        days_before_now_2 = now_datetime.shift(days=-2)
        days_before_now_3 = now_datetime.shift(days=-3)

        for model in [models.SNSTask, models.SQSTask, models.CeleryTask]:
            with freezegun.freeze_time(days_before_now_3.datetime):
                task_days_ago_3 = model.objects.create(
                    state=constants.TaskStates.SUCCEEDED,
                )
            with freezegun.freeze_time(days_before_now_2.datetime):
                task_days_ago_2 = model.objects.create(
                    state=constants.TaskStates.SUCCEEDED,
                )
            with freezegun.freeze_time(days_before_now_1.datetime):
                task_days_ago_1 = model.objects.create(
                    state=constants.TaskStates.SUCCEEDED,
                )

            with freezegun.freeze_time(now_datetime.datetime):
                call_command('atomic_cleanup_old_tasks', '--days=2')
                # Since we pass in 2 to the "days" arg, only the task created 3 days
                # ago should be deleted
                self.assertFalse(model.objects.filter(id=task_days_ago_3.id).exists())
                self.assertTrue(model.objects.filter(id=task_days_ago_2.id).exists())
                self.assertTrue(model.objects.filter(id=task_days_ago_1.id).exists())

    def test_days_default_works(self):
        now_datetime = arrow.utcnow()
        days_before_now_1 = now_datetime.shift(days=-1)
        days_before_now_30 = now_datetime.shift(days=-30)
        days_before_now_31 = now_datetime.shift(days=-31)

        for model in [models.SNSTask, models.SQSTask, models.CeleryTask]:
            with freezegun.freeze_time(days_before_now_31.datetime):
                task_days_ago_31 = model.objects.create(
                    state=constants.TaskStates.DELETED,
                )
            with freezegun.freeze_time(days_before_now_30.datetime):
                task_days_ago_30 = model.objects.create(
                    state=constants.TaskStates.DELETED,
                )
            with freezegun.freeze_time(days_before_now_1.datetime):
                task_days_ago_1 = model.objects.create(
                    state=constants.TaskStates.DELETED,
                )

            with freezegun.freeze_time(now_datetime.datetime):
                call_command('atomic_cleanup_old_tasks')
                # Since we don't pass in the "days" arg, it defaults to 30.
                # Only the task created 31 days ago should be deleted
                self.assertFalse(model.objects.filter(id=task_days_ago_31.id).exists())
                self.assertTrue(model.objects.filter(id=task_days_ago_30.id).exists())
                self.assertTrue(model.objects.filter(id=task_days_ago_1.id).exists())
