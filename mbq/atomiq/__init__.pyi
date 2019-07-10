from typing import Callable

from mbq import metrics


sns_publish: Callable[..., None]
sqs_producer: Callable[..., None]
celery_publish: Callable[..., None]

_collector: metrics.Collector
