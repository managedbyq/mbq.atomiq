from django.db import transaction
from django.test import TestCase

from mbq.atomiq import producers, test_utils
from tests.compat import mock


class CeleryTestUtilsTest(TestCase):

    def setUp(cls):
        cls.task = mock.Mock()
        cls.task.name = 'test_task_name'
        with transaction.atomic():
            producers.CeleryProducer().publish(
                cls.task, 1, 'a', 3.1, [], {},  kwarg1=2, kwarg2='b', kwarg3=3.14, kwarg4=[1, 2, {}]
            )

    def test_pass_in_args_and_kwargs(self):
        self.assertTrue(test_utils.celery_publish_call(
            self.task, 1, 'a', 3.1, [], {},  kwarg1=2, kwarg2='b', kwarg3=3.14, kwarg4=[1, 2, {}]
        ))
        self.assertFalse(test_utils.celery_publish_call(self.task, 2, 'a', kwarg='c'))

    def test_only_pass_in_task(self):
        self.assertTrue(test_utils.celery_publish_call(self.task))

        task2 = mock.Mock()
        task2.name = 'test_task_name_2'
        self.assertFalse(test_utils.celery_publish_call(task2))


class SNSTestUtilsTest(TestCase):

    def setUp(cls):
        cls.payload = [
            {'a': 1, 'b': 'b', 'c': 3.1, 'd': [], 'e': {}},
            {'f': 2, 'g': 'g', 'h': 4.2, 'i': [], 'j': {}},
        ]
        with transaction.atomic():
            producers.SNSProducer().publish('topic_arn', cls.payload)

    def test_pass_in_payload(self):
        self.assertTrue(test_utils.sns_publish_call('topic_arn', self.payload))
        self.assertFalse(test_utils.sns_publish_call('topic_arn2', self.payload))
        self.assertFalse(test_utils.sns_publish_call('topic_arn', self.payload + [{}]))

    def test_only_pass_in_topic(self):
        self.assertTrue(test_utils.sns_publish_call('topic_arn'))
        self.assertFalse(test_utils.sns_publish_call('topic_arn2'))


class SQSTestUtilsTest(TestCase):

    def setUp(cls):
        cls.payload = [
            {'a': 1, 'b': 'b', 'c': 3.1, 'd': [], 'e': {}},
            {'f': 2, 'g': 'g', 'h': 4.2, 'i': [], 'j': {}},
        ]
        with transaction.atomic():
            producers.SQSProducer().publish('queue_url', cls.payload)

    def test_pass_in_payload(self):
        self.assertTrue(test_utils.sqs_publish_call('queue_url', self.payload))
        self.assertFalse(test_utils.sqs_publish_call('queue_url2', self.payload))
        self.assertFalse(test_utils.sqs_publish_call('queue_url', self.payload + [{}]))

    def test_only_pass_in_queue(self):
        self.assertTrue(test_utils.sqs_publish_call('queue_url'))
        self.assertFalse(test_utils.sqs_publish_call('queue_url2'))
