from unittest import mock

from django.core.management import call_command
from django.test import TestCase

import arrow
from mbq.atomiq import constants, exceptions, models
from mbq.atomiq.management.commands import atomic_run_consumer

import freezegun


@mock.patch('mbq.atomiq.management.commands.atomic_run_consumer.SignalHandler')
class RunConsumerCommandTest(TestCase):

    @mock.patch('mbq.atomiq.consumers.SNSConsumer.process_one_task')
    def test_run_consumer_sns(self, process_one_task, SignalHandlerMock):
        SignalHandlerMock.return_value.should_continue.side_effect = [True, True, False]
        process_one_task.return_value = models.SNSTask.objects.create()
        call_command('atomic_run_consumer', '--queue=sns')
        self.assertEqual(process_one_task.call_count, 2)

    @mock.patch('mbq.atomiq.consumers.SQSConsumer.process_one_task')
    def test_run_consumer_sqs(self, process_one_task, SignalHandlerMock):
        SignalHandlerMock.return_value.should_continue.side_effect = [True, True, False]
        process_one_task.return_value = models.SNSTask.objects.create()
        call_command('atomic_run_consumer', '--queue=sqs')
        self.assertEqual(process_one_task.call_count, 2)

    @mock.patch('mbq.atomiq.consumers.CeleryConsumer.process_one_task')
    def test_run_consumer_celery(self, process_one_task, SignalHandlerMock):
        SignalHandlerMock.return_value.should_continue.side_effect = [True, True, False]
        process_one_task.return_value = models.SNSTask.objects.create()
        call_command('atomic_run_consumer', '--queue=celery', '--celery-app=tests.celery')
        self.assertEqual(process_one_task.call_count, 2)

    @mock.patch('mbq.atomiq.management.commands.atomic_run_consumer.sleep')
    @mock.patch('mbq.atomiq.consumers.CeleryConsumer.process_one_task')
    def test_sleeps_when_queue_is_empty(self, process_task, sleep, SignalHandlerMock):
        SignalHandlerMock.return_value.should_continue.side_effect = [True, False]
        process_task.side_effect = exceptions.NoAvailableTasksToProcess
        call_command('atomic_run_consumer', '--queue=sqs')
        self.assertEqual(sleep.call_count, 1)

    @mock.patch('mbq.atomiq.management.commands.atomic_run_consumer.sleep')
    @mock.patch('mbq.atomiq.consumers.CeleryConsumer.process_one_task')
    def test_sleeps_on_unexpected_error(self, process_task, sleep, SignalHandlerMock):
        SignalHandlerMock.return_value.should_continue.side_effect = [True, False]
        process_task.side_effect = Exception
        call_command('atomic_run_consumer', '--queue=sqs')
        self.assertEqual(sleep.call_count, 1)


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


@mock.patch('mbq.metrics.Collector.timing')
@mock.patch('mbq.metrics.Collector.increment')
class CollectMetricsTest(TestCase):

    @freezegun.freeze_time()
    def test_collect_metrics_success(self, increment, timing):
        command = atomic_run_consumer.Command()
        task = models.SNSTask.objects.create(
            state=constants.TaskStates.SUCCEEDED,
            visible_after=arrow.utcnow().shift(seconds=0.012).datetime,
            succeeded_at=arrow.utcnow().shift(seconds=0.471).datetime
        )
        expected_tags = {
            'end_state': constants.TaskStates.SUCCEEDED,
            'result': 'success',
            'queue_type': constants.QueueType.SNS,
        }

        execution_started_at = arrow.utcnow().shift(seconds=0.123).datetime
        execution_ended_at = arrow.utcnow().shift(seconds=0.579).datetime

        command.collect_task_metrics(
            constants.QueueType.SNS,
            task,
            execution_started_at,
            execution_ended_at,
        )

        increment.assert_called_once_with(
            'task',
            tags=expected_tags,
        )

        wait_time = mock.call(
            'task.wait_time_ms',
            111.0,
            tags=expected_tags
        )
        execution_time = mock.call(
            'task.execution_time_ms',
            456.0,
            tags=expected_tags
        )

        turnaround_time = mock.call(
            'task.turnaround_time_ms',
            471.0,
            tags=expected_tags
        )

        self.assertEqual(timing.call_count, 3)
        timing.assert_has_calls([wait_time, execution_time, turnaround_time])

    @freezegun.freeze_time()
    def test_collect_metrics_error(self, increment, timing):
        command = atomic_run_consumer.Command()

        task = models.SNSTask.objects.create(
            visible_after=arrow.utcnow().shift(seconds=0.012).datetime,
        )
        expected_tags = {
            'end_state': constants.TaskStates.ENQUEUED,
            'result': 'error',
            'queue_type': 'sns',
        }

        execution_started_at = arrow.utcnow().shift(seconds=0.123).datetime
        execution_ended_at = arrow.utcnow().shift(seconds=0.579).datetime

        command.collect_task_metrics(
            constants.QueueType.SNS,
            task,
            execution_started_at,
            execution_ended_at,
        )

        increment.assert_called_once_with(
            'task',
            tags=expected_tags,
        )

        wait_time = mock.call(
            'task.wait_time_ms',
            111.0,
            tags=expected_tags
        )
        execution_time = mock.call(
            'task.execution_time_ms',
            456.0,
            tags=expected_tags
        )

        self.assertEqual(timing.call_count, 2)
        timing.assert_has_calls([wait_time, execution_time])
