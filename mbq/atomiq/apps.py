from django.apps import AppConfig


class AtomiqConfig(AppConfig):
    name = 'mbq.atomiq'
    verbose_name = 'Atomiq'

    def ready(self):
        from django.conf import settings
        from django.core.exceptions import ImproperlyConfigured
        import mbq.metrics
        from . import producers

        service = settings.ATOMIQ.get('service')
        env = settings.ATOMIQ.get('env')

        if not service:
            raise ImproperlyConfigured(
                'mbq.atomiq must be initialized with a service name.\n'
                'Please make sure you have an ATOMIQ constant with a "service" field '
                'in your Django settings.'
            )
        if not env:
            raise ImproperlyConfigured(
                'mbq.atomiq must be initialized with an environment.\n'
                'Please make sure you have an ATOMIQ constant with a "env" field '
                'in your Django settings.'
            )

        self.module._collector = mbq.metrics.Collector(
            namespace='mbq.atomiq',
            tags={'env': env, 'service': service, 'atomiq_service_name': service},
        )

        sns_producer = producers.SNSProducer()
        self.module.sns_publish = sns_producer.publish
        sqs_producer = producers.SQSProducer()
        self.module.sqs_publish = sqs_producer.publish
        celery_producer = producers.CeleryProducer()
        self.module.celery_publish = celery_producer.publish
