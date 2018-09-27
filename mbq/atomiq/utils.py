from functools import wraps
import inspect
import time

from django.db import transaction
from django.test import TestCase


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

        @wraps(func)
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
    instances of django.test.TestCase. If we find TestCase unit test, then we expect there to be
    TWO transactions created by Django, and ONE transaction created by the user.

    Thanks for listening.
    Your pal,

    Per-Andre

    """
    in_setup = False
    in_test_case = False

    db_connection = transaction.get_connection()

    # This loops through the call stack and sets "in_setup" and "in_test_case"
    for stack_frame in inspect.stack():
        for local_var in stack_frame[0].f_locals.values():
            if stack_frame[3] in ['setUpTestData', 'setUpclass']:
                in_setup = True

            if not local_var:
                continue

            if inspect.isclass(local_var) and issubclass(local_var, TestCase):
                in_test_case = True
            else:
                var_class = getattr(local_var, '__class__', None)
                if inspect.isclass(var_class) and issubclass(var_class, TestCase):
                    in_test_case = True

    if in_test_case:
        if in_setup:
            # 0 savepoint IDs implies there is only 1 transaction. We expect 2:
            # one from setUpclass and one user transaction.
            if len(db_connection.savepoint_ids) == 0:
                return False
        elif len(db_connection.savepoint_ids) in [0, 1]:
            # One savepoint ID implies there are 2 transactions.
            # Here we expect 3 transactions:
            # one from setUpClass, one wrapping the unit test, and one user transaction.
            return False

    return True
