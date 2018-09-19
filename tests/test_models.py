from django.test import TestCase

import arrow
import freezegun
from mbq.atomiq.constants import TaskStates
from mbq.atomiq.models import SNSTask


class TaskTest(TestCase):

    @freezegun.freeze_time()
    def test_available_for_processing_queryset(self):
        task_succeeded = SNSTask.objects.create(state=TaskStates.SUCCEEDED)
        task_failed = SNSTask.objects.create(state=TaskStates.FAILED)
        task_deleted = SNSTask.objects.create(state=TaskStates.DELETED)

        task_ready = SNSTask.objects.create(state=TaskStates.ENQUEUED)
        task_ready_past = SNSTask.objects.create(
            state=TaskStates.ENQUEUED,
            visible_after=arrow.utcnow().shift(seconds=-1).datetime,
        )
        task_ready_now = SNSTask.objects.create(
            state=TaskStates.ENQUEUED,
            visible_after=arrow.utcnow().datetime,
        )
        task_ready_future = SNSTask.objects.create(
            state=TaskStates.ENQUEUED,
            visible_after=arrow.utcnow().shift(seconds=1).datetime,
        )

        tasks = SNSTask.objects.available_for_processing()
        self.assertEquals(list(tasks), [
            task_ready_past,
            task_ready,
            task_ready_now,
        ])
