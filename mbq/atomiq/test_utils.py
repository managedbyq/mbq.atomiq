from . import constants, models


def celery_publish_call(task, *args, **kwargs):
    tasks = models.CeleryTask.objects.filter(
        state=constants.TaskStates.ENQUEUED,
        task_name=task.name,
    )
    if args or kwargs:
        tasks = tasks.filter(
            task_arguments={
                'args': args,
                'kwargs': kwargs,
            }
        )
    return tasks.exists()


def sns_publish_call(topic_arn, payload=None):
    tasks = models.SNSTask.objects.filter(
        state=constants.TaskStates.ENQUEUED,
        topic_arn=topic_arn,
    )
    if payload:
        tasks = tasks.filter(payload=payload)

    return tasks.exists()


def sqs_publish_call(queue_url, payload=None):
    tasks = models.SQSTask.objects.filter(
        state=constants.TaskStates.ENQUEUED,
        queue_url=queue_url,
    )
    if payload:
        tasks = tasks.filter(payload=payload)

    return tasks.exists()
