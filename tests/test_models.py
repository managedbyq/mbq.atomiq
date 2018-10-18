from django.test import TestCase

import arrow
from mbq.atomiq.constants import TaskStates
from mbq.atomiq.models import SNSTask

import freezegun


class TaskTest(TestCase):

    @freezegun.freeze_time()
    def test_available_for_processing_queryset(self):
        # successfull task
        SNSTask.objects.create(state=TaskStates.SUCCEEDED)
        # failed task
        SNSTask.objects.create(state=TaskStates.FAILED)
        # deleted task
        SNSTask.objects.create(state=TaskStates.DELETED)

        task_ready_past = SNSTask.objects.create(
            state=TaskStates.ENQUEUED,
            visible_after=arrow.utcnow().shift(seconds=-1).datetime,
        )
        task_ready_now = SNSTask.objects.create(
            state=TaskStates.ENQUEUED,
            visible_after=arrow.utcnow().datetime,
        )
        # future task
        SNSTask.objects.create(
            state=TaskStates.ENQUEUED,
            visible_after=arrow.utcnow().shift(seconds=1).datetime,
        )

        tasks = SNSTask.objects.available_for_processing()
        # import pdb; pdb.set_trace()
        self.assertEquals(list(tasks), [
            task_ready_past,
            task_ready_now,
        ])
