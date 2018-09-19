import os

import dj_database_url


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
