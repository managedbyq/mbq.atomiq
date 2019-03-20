import os

import boto3
import dj_database_url

from mbq import env, metrics


SECRET_KEY = 'fake-key'
DEBUG = True
ATOMIQ = {
    'env': 'Test',
    'service': 'test-service',
}

database_url = os.environ.get('DATABASE_URL', 'mysql://root:@mysql:3306/atomiqdb')
DATABASES = {
    'default': dj_database_url.parse(database_url),
}

INSTALLED_APPS = [
    'mbq.atomiq',
]

USE_TZ = True

boto3.setup_default_session(
    region_name='us-east-1',
)

ENV = env.get_environment("ENV_NAME")

metrics.init('mbq.atomiq', env=ENV, constant_tags={"env": ENV.long_name})
