# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-09-17 18:38
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone
import jsonfield.fields
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CeleryTask',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('succeeded_at', models.DateTimeField(null=True)),
                ('deleted_at', models.DateTimeField(null=True)),
                ('failed_at', models.DateTimeField(null=True)),
                ('number_of_attempts', models.PositiveIntegerField(default=0)),
                ('visible_after', models.DateTimeField(default=django.utils.timezone.now)),
                ('error_message', models.TextField(null=True)),
                ('stacktrace', models.TextField(null=True)),
                ('state', models.CharField(choices=[('enqueued', 'Enqueued'), ('succeeded', 'Succeeded'), ('failed', 'Failed'), ('deleted', 'Deleted')], default='enqueued', max_length=256)),
                ('task_name', models.CharField(max_length=256)),
                ('task_arguments', jsonfield.fields.JSONField()),
            ],
            options={
                'verbose_name': 'Celery Task',
            },
        ),
        migrations.CreateModel(
            name='SNSTask',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('succeeded_at', models.DateTimeField(null=True)),
                ('deleted_at', models.DateTimeField(null=True)),
                ('failed_at', models.DateTimeField(null=True)),
                ('number_of_attempts', models.PositiveIntegerField(default=0)),
                ('visible_after', models.DateTimeField(default=django.utils.timezone.now)),
                ('error_message', models.TextField(null=True)),
                ('stacktrace', models.TextField(null=True)),
                ('state', models.CharField(choices=[('enqueued', 'Enqueued'), ('succeeded', 'Succeeded'), ('failed', 'Failed'), ('deleted', 'Deleted')], default='enqueued', max_length=256)),
                ('topic_arn', models.CharField(max_length=256)),
                ('payload', jsonfield.fields.JSONField()),
            ],
            options={
                'verbose_name': 'SNS Task',
            },
        ),
        migrations.CreateModel(
            name='SQSTask',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('succeeded_at', models.DateTimeField(null=True)),
                ('deleted_at', models.DateTimeField(null=True)),
                ('failed_at', models.DateTimeField(null=True)),
                ('number_of_attempts', models.PositiveIntegerField(default=0)),
                ('visible_after', models.DateTimeField(default=django.utils.timezone.now)),
                ('error_message', models.TextField(null=True)),
                ('stacktrace', models.TextField(null=True)),
                ('state', models.CharField(choices=[('enqueued', 'Enqueued'), ('succeeded', 'Succeeded'), ('failed', 'Failed'), ('deleted', 'Deleted')], default='enqueued', max_length=256)),
                ('queue_url', models.CharField(max_length=256)),
                ('payload', jsonfield.fields.JSONField()),
            ],
            options={
                'verbose_name': 'SQS Task',
            },
        ),
    ]
