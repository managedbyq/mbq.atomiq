from . import constants, models


def get_celery_publish_args(task):
    tasks = models.CeleryTask.objects.filter(
        state=constants.TaskStates.ENQUEUED,
        task_name=task.name,
    )
    return [task.task_arguments for task in tasks]


def get_sns_publish_payloads(topic_arn):
    tasks = models.SNSTask.objects.filter(
        state=constants.TaskStates.ENQUEUED,
        topic_arn=topic_arn,
    )
    return [task.payload for task in tasks]


def reset_celery_publishes(task):
    models.CeleryTask.objects.filter(
        state=constants.TaskStates.ENQUEUED,
        task_name=task.name,
    ).delete()


def reset_sns_publishes(topic_arn):
    models.SNSTask.objects.filter(
        state=constants.TaskStates.ENQUEUED,
        topic_arn=topic_arn,
    ).delete()
