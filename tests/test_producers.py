import uuid

from django.db import transaction
from django.test import SimpleTestCase, TestCase

import arrow
import mbq.atomiq
from mbq.atomiq import constants, exceptions, models, producers
from tests.compat import mock


class TransactionCheckTest(SimpleTestCase):
    allow_database_queries = True

    def test_outside_of_transaction(self):
        producer = producers.BaseProducer()
        self.assertFalse(producer._is_running_within_transaction())


class SNSProducerTest(TestCase):
    def test_outside_of_transaction(self):
        with self.assertRaises(exceptions.TransactionError):
            mbq.atomiq.sns_publish('topic_arn', {'payload': 'payload'})

    def test_non_json_serializable_payload(self):
        bad_payload = {
            'arrow_obj': arrow.utcnow(),
        }

        with self.assertRaises(TypeError):
            with transaction.atomic():
                mbq.atomiq.sns_publish('topic_arn', bad_payload)

    def test_message_enqueued(self):
        unique_topic_arn = uuid.uuid4()
        payload = {'payload': 'payload'}
        with transaction.atomic():
            mbq.atomiq.sns_publish(unique_topic_arn, payload)

        created_task = models.SNSTask.objects.get(topic_arn=unique_topic_arn)
        self.assertEqual(created_task.number_of_attempts, 0)
        self.assertIsNotNone(created_task.visible_after)
        self.assertIsNone(created_task.succeeded_at)
        self.assertIsNone(created_task.deleted_at)
        self.assertIsNone(created_task.failed_at)
        self.assertEqual(created_task.state, constants.TaskStates.ENQUEUED)
        self.assertEqual(created_task.payload, payload)


class SQSProducerTest(TestCase):
    def test_outside_of_transaction(self):
        with self.assertRaises(exceptions.TransactionError):
            mbq.atomiq.sqs_publish('queue_url', {'payload': 'payload'})

    def test_non_json_serializable_payload(self):
        bad_payload = {
            'arrow_obj': arrow.utcnow(),
        }

        with self.assertRaises(TypeError):
            with transaction.atomic():
                mbq.atomiq.sqs_publish('queue_url', bad_payload)

    def test_message_enqueued(self):
        unique_queue_url = uuid.uuid4()
        payload = {'payload': 'payload'}
        with transaction.atomic():
            mbq.atomiq.sqs_publish(unique_queue_url, payload)

        created_task = models.SQSTask.objects.get(queue_url=unique_queue_url)
        self.assertEqual(created_task.number_of_attempts, 0)
        self.assertIsNotNone(created_task.visible_after)
        self.assertIsNone(created_task.succeeded_at)
        self.assertIsNone(created_task.deleted_at)
        self.assertIsNone(created_task.failed_at)
        self.assertEqual(created_task.state, constants.TaskStates.ENQUEUED)
        self.assertEqual(created_task.payload, payload)


class CeleryProducerTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(CeleryProducerTest, cls).setUpClass()
        cls.mock_task = mock.Mock()

    def test_outside_of_transaction(self):
        with self.assertRaises(exceptions.TransactionError):
            mbq.atomiq.celery_publish(self.mock_task)

    def test_non_json_serializable_payload(self):
        bad_arg = arrow.utcnow()

        with self.assertRaises(TypeError):
            with transaction.atomic():
                mbq.atomiq.celery_publish(self.mock_task, bad_arg)

    def test_message_enqueued(self):
        unique_task_name = uuid.uuid4()
        self.mock_task.name = unique_task_name

        args = [1, 2, True, 'test']
        kwargs = {
            'a': 'foo',
            'b': 20,
            'c': False,
        }

        with transaction.atomic():
            mbq.atomiq.celery_publish(self.mock_task, *args, **kwargs)

        created_task = models.CeleryTask.objects.get(task_name=unique_task_name)
        self.assertEqual(created_task.number_of_attempts, 0)
        self.assertIsNotNone(created_task.visible_after)
        self.assertIsNone(created_task.succeeded_at)
        self.assertIsNone(created_task.deleted_at)
        self.assertIsNone(created_task.failed_at)
        self.assertEqual(created_task.state, constants.TaskStates.ENQUEUED)
        self.assertEqual(created_task.task_arguments, {
            'args': args,
            'kwargs': kwargs,
        })