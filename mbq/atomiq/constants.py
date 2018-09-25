class TaskStates(object):
    ENQUEUED = 'enqueued'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    DELETED = 'deleted'

    CHOICES = (
        (ENQUEUED, 'Enqueued'),
        (SUCCEEDED, 'Succeeded'),
        (FAILED, 'Failed'),
        (DELETED, 'Deleted'),
    )


class QueueType(object):
    SNS = 'sns'
    SQS = 'sqs'
    CELERY = 'celery'

    CHOICES = (
        (SNS, 'SNS'),
        (SQS, 'SQS'),
        (CELERY, 'Celery'),
    )


MAX_ATTEMPTS_TO_PROCESS_TASKS = 3


DEFAULT_DAYS_TO_KEEP_OLD_TASKS = 30
