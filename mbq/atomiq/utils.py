import functools
import inspect
import time

from django.db import transaction
from django.test import TestCase

import rollbar


def time_difference_ms(start_datetime, end_datetime):
    diff_in_seconds = (end_datetime - start_datetime).total_seconds()
    return round(diff_in_seconds * 1000)


def debounce(seconds=None, minutes=None, hours=None):
    def wrapper(func):
        func.seconds_between_runs = 0
        func.last_run = time.time()

        if seconds:
            func.seconds_between_runs += seconds
        if minutes:
            func.seconds_between_runs += minutes * 60
        if hours:
            func.seconds_between_runs += hours * 60 * 60

        @functools.wraps(func)
        def wrapped_func(*args, **kwargs):
            if func.last_run + func.seconds_between_runs < time.time():
                func(*args, **kwargs)
                func.last_run = time.time()

        return wrapped_func
    return wrapper


def has_user_transactions_in_django_test_case():
    """
    Atomiq publish will throw an exception if not used within a transaction, and we want
    to make sure nobody ships code that is going to throw this exception in production.
    The problem is that Django TestCase wraps all test functions in a transaction, which
    masks this error. Therefore, we use this function to ~inspect~ ~the~ ~stack~ and look for
    instances of django.test.TestCase.

    1. If we are in a TestCase unit test function, we expect to find 3 transactions total:
    two created by Django and one by the user.

    2. If we are in the TestCase setUpClass function, we expect to find 2 transactions:
    one created by Django and by the user.

    Thanks for listening.
    Your pal,

    Per-Andre

    """
    in_testcase_setupclass = False
    in_testcase = False
    db_connection = transaction.get_connection()
    if not db_connection.in_atomic_block:
        return False

    for frame in inspect.stack():
        if frame[3] == 'setUpClass':
            if _frame_locals_contains_testcase_class(frame):
                in_testcase_setupclass = True
                in_testcase = True
                break

        if _frame_locals_contains_testcase_instance(frame):
            in_testcase = True

    number_of_transactions = len(db_connection.savepoint_ids) + 1
    if in_testcase_setupclass:
        if number_of_transactions < 2:
            return False
    elif in_testcase:
        if number_of_transactions < 3:
            return False

    return True


def _frame_locals_contains_testcase_instance(frame):
    for local_var in frame[0].f_locals.values():
        if isinstance(local_var, TestCase):
            return True

    return False


def _frame_locals_contains_testcase_class(frame):
    for local_var in frame[0].f_locals.values():
        if inspect.isclass(local_var) and issubclass(local_var, TestCase):
            return True

    return False


def send_errors_to_rollbar(func):

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception:
            rollbar.report_exc_info()
            raise

    return wrapper
