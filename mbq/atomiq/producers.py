import importlib
import logging
import sys

from django.db import transaction

from . import exceptions, models


logger = logging.getLogger(__name__)


RUNNING_TESTS = any('test' in arg for arg in sys.argv)


class BaseProducer(object):
    required_dependencies = []
    _dependencies_confirmed = False

    def _dependencies_check(self):
        if self._dependencies_confirmed:
            return

        missing_dependencies = []
        for module_name in self.required_dependencies:
            try:
                importlib.import_module(module_name)
            except ImportError:
                missing_dependencies.append(module_name)

        if missing_dependencies:
            msg = 'Missing dependencies for this queue type: {}'.format(
                ', '.join(missing_dependencies)
            )
            raise ImportError(msg)

        self._dependencies_confirmed = True

    def _is_running_within_transaction(self):
        db_connection = transaction.get_connection()

        if not db_connection.in_atomic_block:
            return False

        """
        Django TestCase  wraps everything in a transaction, but we still want to
        make unit tests fail without an explicit atomic transaction definition.
        So when we're running in test mode, we are going to check the number of existing
        save points and expect there at least to be 2: 1 from TestCase and 1 user-defined.
        """
        if RUNNING_TESTS:
            import inspect
            from django.test import TestCase
            inSetup = False
            inTestCase = False

            # This loops through the call stack and sets "isSetUp" and "isTestCase"
            for stack_frame in inspect.stack():
                frame = stack_frame[0]
                localVars = frame.f_locals
                selfVar = localVars.get('self')
                if selfVar:
                    selfClass = getattr(selfVar, '__class__')
                    if inspect.isclass(selfClass) and issubclass(selfClass, TestCase):
                        inTestCase = True

                clsClass = localVars.get('cls')
                if inspect.isclass(clsClass) and issubclass(clsClass, TestCase):
                    inTestCase = True

                if stack_frame[3] in ['setUpTestData', 'setUp', 'setUpClass']:
                    inSetup = True

            if inTestCase:
                if inSetup:
                    # Don't enforce transactions in TestCase setup functions
                    return True

                elif len(db_connection.savepoint_ids) < 2:
                    # Enforce 1 user transaction in TestCase unit tests
                    return False

        return True

    def _transaction_check(self):
        if not self._is_running_within_transaction():
            raise exceptions.TransactionError(
                'Atomic publish needs to happen within a db transaction.'
            )

    def publish(self, *args, **kwargs):
        self._dependencies_check()
        self._transaction_check()
        task = self._create_task(*args, **kwargs)
        logger.info('task created: {task_id}'.format(task_id=task.uuid))

    def _create_task(self, *args, **kwargs):
        raise NotImplementedError('create_task must be implemented by producer subclasses.')


class SNSProducer(BaseProducer):
    required_dependencies = ['boto3']

    def _create_task(self, topic_arn, payload):
        return models.SNSTask.objects.create(
            topic_arn=topic_arn,
            payload=payload,
        )


class SQSProducer(BaseProducer):
    required_dependencies = ['boto3']

    def _create_task(self, queue_url, payload):
        return models.SQSTask.objects.create(
            queue_url=queue_url,
            payload=payload,
        )


class CeleryProducer(BaseProducer):
    required_dependencies = ['celery']

    def _create_task(self, task, *args, **kwargs):
        return models.CeleryTask.objects.create(
            task_name=task.name,
            task_arguments={
                'args': args,
                'kwargs': kwargs,
            }
        )
