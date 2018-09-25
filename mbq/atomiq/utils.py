import time

from functools import wraps


def time_difference_ms(start_datetime, end_datetime):
    diff_in_seconds = (end_datetime - start_datetime).total_seconds()
    return round(diff_in_seconds * 1000)


def debounce(seconds=None, minutes=None, hours=None):
    def wrapper(func):
        last_run = 0
        seconds_between_runs = 0

        if seconds:
            seconds_between_runs += seconds
        if minutes:
            seconds_between_runs += minutes * 60
        if hours:
            seconds_between_runs += hours * 60 * 60

        @wraps(func)
        def wrapped_func(*args, **kwargs):
            now = time.time()

            if last_run + seconds_between_runs < now:
                last_run = now
                return func(*args, **kwargs)

            return

        return wrapped_func
    return wrapper
