from django.test import TestCase

import arrow
from mbq.atomiq import consumers
from mbq.atomiq.constants import MAX_ATTEMPTS_TO_PROCESS_TASKS, TaskStates
from mbq.atomiq.models import SNSTask
from tests.compat import mock

import freezegun


@mock.patch('mbq.atomiq.consumers.SNSConsumer.publish')
class ProcessTasksTest(TestCase):

    def setUp(self):
        freezer = freezegun.freeze_time()
        freezer.start()
        self.addCleanup(freezer.stop)

        self.task_ready = SNSTask.objects.create(state=TaskStates.ENQUEUED)
        self.task_ready_past = SNSTask.objects.create(
            state=TaskStates.ENQUEUED,
            visible_after=arrow.utcnow().shift(seconds=-3).datetime,
        )
        self.task_ready_now = SNSTask.objects.create(
            state=TaskStates.ENQUEUED,
            visible_after=arrow.utcnow().datetime,
        )
        self.consumer = consumers.SNSConsumer()

    def test_process_tasks_successfully(self, publish):

        self.consumer.process_task(self.task_ready)
        self.assertEquals(self.task_ready.state, TaskStates.SUCCEEDED)
        self.assertEquals(self.task_ready.number_of_attempts, 1)
        self.assertEquals(self.task_ready.succeeded_at, arrow.utcnow().datetime)

        self.consumer.process_task(self.task_ready_past)
        self.assertEquals(self.task_ready_past.state, TaskStates.SUCCEEDED)
        self.assertEquals(self.task_ready_past.number_of_attempts, 1)
        self.assertEquals(self.task_ready_past.succeeded_at, arrow.utcnow().datetime)

    def test_process_tasks_with_requeue(self, publish):
        # Makes publish raise an exception so the tasks fail
        publish.side_effect = Exception
        self.consumer.process_task(self.task_ready)
        expected_visible_after = arrow.utcnow().shift(seconds=2)

        # These tasks should be processed and an exception will raise in the publish
        # function. They should be requeued with a visible_after in the future
        self.assertEquals(self.task_ready.state, TaskStates.ENQUEUED)
        self.assertEquals(self.task_ready.number_of_attempts, 1)
        self.assertEquals(self.task_ready.succeeded_at, None)
        self.assertEquals(self.task_ready.visible_after, expected_visible_after)

        # This task has a visible_after which is in the past, so it should be requeued
        # the same way as the first task.
        self.consumer.process_task(self.task_ready_past)
        self.assertEquals(self.task_ready_past.state, TaskStates.ENQUEUED)
        self.assertEquals(self.task_ready_past.number_of_attempts, 1)
        self.assertEquals(self.task_ready_past.visible_after, expected_visible_after)
        self.assertEquals(self.task_ready_past.succeeded_at, None)

    def test_process_tasks_with_final_failure(self, publish):
        # Change number_of_attempts so the consumer thinks this is the last retry
        self.task_ready.number_of_attempts = MAX_ATTEMPTS_TO_PROCESS_TASKS
        self.task_ready_past.number_of_attempts = MAX_ATTEMPTS_TO_PROCESS_TASKS

        # Makes publish raise an exception so the tasks fail
        publish.side_effect = Exception('Test Error Message')
        self.consumer.process_task(self.task_ready)

        # These tasks should be processed with an exception raised in the publish function.
        # Since they have already been retried the max number of times,
        # they should be transitioned to the FAILED state.
        self.assertEquals(self.task_ready.state, TaskStates.FAILED)
        self.assertEquals(self.task_ready.number_of_attempts, MAX_ATTEMPTS_TO_PROCESS_TASKS + 1)
        self.assertEquals(self.task_ready.failed_at, arrow.utcnow().datetime)
        self.assertEquals(self.task_ready.error_message, 'Test Error Message')
        # A hacky way of testing that the stacktrace field is being set to something
        # that is likely an actual stacktrace.
        # Using assertEquals on the stacktrace field would be a very brittle test,
        # since refactoring the code would change the stacktrace and break the tests.
        self.assertTrue(
            'Traceback (most recent call last):' in self.task_ready.stacktrace
        )

        self.consumer.process_task(self.task_ready_past)
        self.assertEquals(self.task_ready_past.state, TaskStates.FAILED)
        self.assertEquals(
            self.task_ready_past.number_of_attempts,
            MAX_ATTEMPTS_TO_PROCESS_TASKS + 1
        )
        self.assertEquals(self.task_ready_past.failed_at, arrow.utcnow().datetime)
        self.assertEquals(self.task_ready_past.error_message, 'Test Error Message')
        self.assertTrue(
            'Traceback (most recent call last):' in self.task_ready_past.stacktrace
        )

    def test_process_tasks_with_final_success(self, sns_publish):
        # Change number_of_attempts so the consumer thinks this is the last retry
        self.task_ready.number_of_attempts = MAX_ATTEMPTS_TO_PROCESS_TASKS
        self.task_ready_past.number_of_attempts = MAX_ATTEMPTS_TO_PROCESS_TASKS

        self.consumer.process_task(self.task_ready)
        # These tasks should be processed successfully and transitioned to SUCCEEDED
        self.assertEquals(self.task_ready.state, TaskStates.SUCCEEDED)
        self.assertEquals(self.task_ready.number_of_attempts, MAX_ATTEMPTS_TO_PROCESS_TASKS + 1)
        self.assertEquals(self.task_ready.succeeded_at, arrow.utcnow().datetime)

        self.consumer.process_task(self.task_ready_past)
        self.assertEquals(self.task_ready_past.state, TaskStates.SUCCEEDED)
        self.assertEquals(
            self.task_ready_past.number_of_attempts,
            MAX_ATTEMPTS_TO_PROCESS_TASKS + 1
        )
        self.assertEquals(self.task_ready_past.succeeded_at, arrow.utcnow().datetime)


@mock.patch('mbq.atomiq.consumers.BaseConsumer.process_task')
class RunConsumerTest(TestCase):

    def setUp(self):
        freezer = freezegun.freeze_time()
        freezer.start()
        self.addCleanup(freezer.stop)

        self.consumer = consumers.SNSConsumer()
        self.topic_arn = 'test_topic_arn'
        self.payload = {'test': 'payload'}

    def test_run_consumer_finds_task(self, process_task):
        task = SNSTask.objects.create(
            state=TaskStates.ENQUEUED,
            topic_arn=self.topic_arn,
            payload=self.payload,
        )

        self.consumer.run()
        process_task.assert_called_once_with(task)

    @mock.patch('mbq.atomiq.consumers.sleep')
    def test_run_consumer_finds_no_tasks_and_sleeps(self, sleep, process_task):
        self.consumer.run()
        process_task.assert_not_called()
        sleep.assert_called_once_with(0.5)

    @mock.patch('mbq.atomiq.consumers.sleep')
    def test_run_consumer_skips_unavailable_tasks_and_sleeps(self, sleep, process_task):
        SNSTask.objects.create(
            state=TaskStates.DELETED,
            topic_arn=self.topic_arn,
            payload=self.payload,
        )
        SNSTask.objects.create(
            state=TaskStates.FAILED,
            topic_arn=self.topic_arn,
            payload=self.payload,
        )
        SNSTask.objects.create(
            state=TaskStates.ENQUEUED,
            visible_after=arrow.utcnow().shift(seconds=2).datetime,
            topic_arn=self.topic_arn,
            payload=self.payload,
        )

        self.consumer.run()
        process_task.assert_not_called()
        sleep.assert_called_once_with(0.5)

    def test_run_consumer_skips_unavailable_tasks(self, process_task):
        SNSTask.objects.create(
            state=TaskStates.DELETED,
            topic_arn=self.topic_arn,
            payload=self.payload,
        )
        SNSTask.objects.create(
            state=TaskStates.FAILED,
            topic_arn=self.topic_arn,
            payload=self.payload,
        )
        SNSTask.objects.create(
            state=TaskStates.ENQUEUED,
            visible_after=arrow.utcnow().shift(seconds=2).datetime,
            topic_arn=self.topic_arn,
            payload=self.payload,
        )

        task_ready_past = SNSTask.objects.create(
            state=TaskStates.ENQUEUED,
            visible_after=arrow.utcnow().shift(seconds=-1).datetime,
            topic_arn=self.topic_arn,
            payload=self.payload,
        )

        SNSTask.objects.create(
            state=TaskStates.ENQUEUED,
            topic_arn=self.topic_arn,
            payload=self.payload,
        )

        self.consumer.run()
        process_task.assert_called_with(task_ready_past)

    @mock.patch('mbq.atomiq.consumers.sleep')
    def test_run_consumer_sleeps_on_unexpected_error(self, sleep, process_task):
        SNSTask.objects.create(
            state=TaskStates.ENQUEUED,
            topic_arn=self.topic_arn,
            payload=self.payload
        )
        process_task.side_effect = Exception
        self.consumer.run()
        self.assertEquals(sleep.call_count, 1)


@mock.patch('mbq.atomiq.consumers.SNSConsumer.publish')
class RequeueForRetryTest(TestCase):

    @freezegun.freeze_time()
    def test_requeue_for_later_retry(self, publish):
        publish.side_effect = Exception
        consumer = consumers.SNSConsumer()
        task = SNSTask.objects.create(state=TaskStates.ENQUEUED)

        consumer.process_task(task)
        expected_visible_after = arrow.utcnow().shift(seconds=2).datetime
        self.assertEquals(task.number_of_attempts, 1)
        self.assertEquals(task.visible_after, expected_visible_after)
        self.assertEquals(task.state, TaskStates.ENQUEUED)

        with freezegun.freeze_time(arrow.utcnow().shift(seconds=5).datetime):
            consumer.process_task(task)
            expected_visible_after = arrow.utcnow().shift(seconds=4)

        self.assertEquals(task.number_of_attempts, 2)
        self.assertEquals(task.visible_after, expected_visible_after)
        self.assertEquals(task.state, TaskStates.ENQUEUED)


@mock.patch('mbq.metrics.Collector.timing')
@mock.patch('mbq.metrics.Collector.increment')
class SendTaskExecutionMetricsTest(TestCase):

    def setUp(self):
        freezer = freezegun.freeze_time()
        freezer.start()
        self.addCleanup(freezer.stop)

        self.task = SNSTask.objects.create(
            state=TaskStates.ENQUEUED,
            number_of_attempts=2,
            visible_after=arrow.utcnow().shift(seconds=0.012).datetime
        )

    def test_send_task_execution_metrics_error(self, increment, timing):
        consumer = consumers.SNSConsumer()
        execution_started_at = arrow.utcnow().shift(seconds=0.123)
        execution_ended_at = arrow.utcnow().shift(seconds=0.579)
        consumer.send_task_execution_metrics(self.task, execution_started_at, execution_ended_at)

        expected_tags = {
            'end_state': TaskStates.ENQUEUED,
            'result': 'error',
            'queue_type': 'sns',
        }

        increment.assert_called_once_with(
            'task',
            tags=expected_tags,
        )

        timing_call1 = mock.call(
            'task.wait_time_ms',
            111.0,
            tags=expected_tags
        )
        timing_call2 = mock.call(
            'task.execution_time_ms',
            456.0,
            tags=expected_tags
        )
        timing.assert_has_calls([timing_call1, timing_call2])

    def test_send_task_execution_metrics_success(self, increment, timing):
        self.task.state = TaskStates.SUCCEEDED
        self.task.succeeded_at = arrow.utcnow().shift(seconds=0.805).datetime
        self.task.save()

        consumer = consumers.SNSConsumer()
        execution_started_at = arrow.utcnow().shift(seconds=0.123)
        execution_ended_at = arrow.utcnow().shift(seconds=0.579)
        consumer.send_task_execution_metrics(self.task, execution_started_at, execution_ended_at)

        expected_tags = {
            'end_state': TaskStates.SUCCEEDED,
            'result': 'success',
            'queue_type': 'sns',
        }

        increment.assert_called_once_with(
            'task',
            tags=expected_tags,
        )

        timing_call1 = mock.call(
            'task.wait_time_ms',
            111.0,
            tags=expected_tags
        )
        timing_call2 = mock.call(
            'task.execution_time_ms',
            456.0,
            tags=expected_tags
        )
        timing_call3 = mock.call(
            'task.turnaround_time_ms',
            805.0,
            tags=expected_tags
        )
        timing.assert_has_calls([timing_call1, timing_call2, timing_call3])
