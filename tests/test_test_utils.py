from unittest import mock

from django.db import transaction
from django.test import TestCase

from mbq.atomiq import producers, test_utils


class CeleryTestUtilsTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.task = mock.Mock()
        cls.task.name = 'test_task_name'

        other_task = mock.Mock()
        other_task.name = 'other_test_task_name'

        producer = producers.CeleryProducer()
        with transaction.atomic():
            producer.publish(cls.task, 1, 'a', 3.1, kwarg1=2, kwarg2='b')
            producer.publish(cls.task, [], {}, (), kwarg3=3.14, kwarg4=[1, {}])
            producer.publish(other_task, 2, 3, 4)

    def test_get_existing_tasks(self):
        celery_publish_args = test_utils.get_celery_publish_args(self.task)
        expected_args = [
            {
                'args': [1, 'a', 3.1],
                'kwargs': {
                    'kwarg1': 2,
                    'kwarg2': 'b',
                }
            },
            {
                'args': [[], {}, []],
                'kwargs': {
                    'kwarg3': 3.14,
                    'kwarg4': [1, {}],
                }
            }
        ]
        self.assertEquals(celery_publish_args, expected_args)

    def test_get_non_existant_task(self):
        nonexistant_task = mock.Mock()
        nonexistant_task.name = 'name'
        celery_publish_args = test_utils.get_celery_publish_args(nonexistant_task)
        self.assertEquals(celery_publish_args, [])


class SNSTestUtilsTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.payload = [
            {'key1': 1, 'key2': 'b', 'key3': 3.1, 'key4': [], 'key5': {}},
            {'key6': 2, 'key7': 'g', 'key8': 4.2, 'key9': [], 'key10': {}},
        ]
        producer = producers.SNSProducer()
        with transaction.atomic():
            producer.publish('topic_arn', cls.payload)
            producer.publish('topic_arn', [{'key1': 'h', 'key2': 'i'}])
            producer.publish('topic_arn2', [{'key1': 'k', 'key2': 'l'}])

    def test_get_existing_tasks(self):
        sns_publish_payloads = test_utils.get_sns_publish_payloads('topic_arn')
        expected_payloads = [
            [
                {'key1': 1, 'key2': 'b', 'key3': 3.1, 'key4': [], 'key5': {}},
                {'key6': 2, 'key7': 'g', 'key8': 4.2, 'key9': [], 'key10': {}},
            ],
            [
                {'key1': 'h', 'key2': 'i'}
            ]
        ]
        self.assertEquals(sns_publish_payloads, expected_payloads)

    def test_get_non_existant_topic(self):
        sns_publish_payloads = test_utils.get_sns_publish_payloads('nonexist_topic')
        self.assertEquals(sns_publish_payloads, [])


class SQSTestUtilsTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.payload = [
            {'key1': 1, 'key2': 'b', 'key3': 3.1, 'key4': [], 'key5': {}},
            {'key6': 2, 'key7': 'g', 'key8': 4.2, 'key9': [], 'key10': {}},
        ]
        producer = producers.SQSProducer()
        with transaction.atomic():
            producer.publish('queue_url', cls.payload)
            producer.publish('queue_url', [{'key1': 'h', 'key2': 'i'}])
            producer.publish('queue_url2', [{'key1': 'k', 'key2': 'l'}])

    def test_get_existing_tasks(self):
        sqs_publish_payloads = test_utils.get_sqs_publish_payloads('queue_url')
        expected_payloads = [
            [
                {'key1': 1, 'key2': 'b', 'key3': 3.1, 'key4': [], 'key5': {}},
                {'key6': 2, 'key7': 'g', 'key8': 4.2, 'key9': [], 'key10': {}},
            ],
            [
                {'key1': 'h', 'key2': 'i'}
            ]
        ]
        self.assertEquals(sqs_publish_payloads, expected_payloads)

    def test_get_non_existant_queue(self):
        sqs_publish_payloads = test_utils.get_sqs_publish_payloads('nonexist_queue')
        self.assertEquals(sqs_publish_payloads, [])
