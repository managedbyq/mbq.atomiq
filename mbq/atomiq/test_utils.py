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


def get_sqs_publish_payloads(queue_url):
    tasks = models.SQSTask.objects.filter(
        state=constants.TaskStates.ENQUEUED,
        queue_url=queue_url,
    )
    return [task.payload for task in tasks]
